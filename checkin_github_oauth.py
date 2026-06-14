#!/usr/bin/env python3
"""
AnyRouter GitHub OAuth check-in.

This workflow is adapted for this repository and references the browser OAuth
approach from https://github.com/liukaizheng/anyrouter-check-in.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

ROOT = Path(__file__).resolve().parent
ACCOUNTS_FILE = ROOT / 'accounts.json'
STORAGE_DIR = ROOT / 'storage-states'
PROVIDER_ORIGIN = os.getenv('ANYROUTER_ORIGIN', 'https://anyrouter.top').rstrip('/')
START_DELAY_MAX_SECONDS = int(os.getenv('START_DELAY_MAX_SECONDS', '1800'))
ACCOUNT_DELAY_MIN_SECONDS = int(os.getenv('ACCOUNT_DELAY_MIN_SECONDS', '120'))
ACCOUNT_DELAY_MAX_SECONDS = int(os.getenv('ACCOUNT_DELAY_MAX_SECONDS', '480'))


def mask_username(username: str) -> str:
	if '@' in username:
		head, tail = username.split('@', 1)
		return f'{head[:2]}***@{tail}'
	return f'{username[:2]}***'


def scrub_url(url: str) -> str:
	return re.sub(r'([?&](?:code|state|client_id)=)[^&]+', r'\1[redacted]', url)


def provider_host() -> str:
	return urlparse(PROVIDER_ORIGIN).netloc


def oauth_query(url: str) -> dict | None:
	parsed = urlparse(url)
	if not parsed.netloc.endswith(provider_host()):
		return None
	query = parse_qs(parsed.query)
	if 'code' in query and 'state' in query:
		return query
	return None


def github_only_storage_state(state: dict) -> dict:
	return {
		'cookies': [cookie for cookie in state.get('cookies', []) if 'github.com' in cookie.get('domain', '')],
		'origins': [origin for origin in state.get('origins', []) if 'github.com' in origin.get('origin', '')],
	}


def load_github_storage_state(path: Path) -> dict:
	return github_only_storage_state(json.loads(path.read_text(encoding='utf-8')))


def load_accounts() -> list[dict]:
	raw = os.getenv('ANYROUTER_GITHUB_ACCOUNTS', '').strip()
	if raw:
		accounts = json.loads(raw)
	elif ACCOUNTS_FILE.exists():
		accounts = json.loads(ACCOUNTS_FILE.read_text(encoding='utf-8'))
	else:
		raise RuntimeError('ANYROUTER_GITHUB_ACCOUNTS is not configured and accounts.json was not found')

	if not isinstance(accounts, list) or not accounts:
		raise RuntimeError('ANYROUTER_GITHUB_ACCOUNTS must be a non-empty JSON array')

	for index, account in enumerate(accounts):
		if not isinstance(account, dict):
			raise RuntimeError(f'account #{index + 1} must be an object')
		account.setdefault('name', f'account-{index + 1}')
		if 'github_username' not in account and 'username' in account:
			account['github_username'] = account['username']
		if 'github_password' not in account and 'password' in account:
			account['github_password'] = account['password']
		if 'totp_secret' not in account and 'totp' in account:
			account['totp_secret'] = account['totp']
		if not account.get('github_username') or not account.get('github_password'):
			raise RuntimeError(f'{account["name"]}: github_username and github_password are required')

	return accounts


def generate_totp(secret: str) -> str:
	clean = (secret or '').strip().replace(' ', '').upper()
	if not clean:
		return ''
	clean += '=' * ((8 - len(clean) % 8) % 8)
	key = base64.b32decode(clean)
	counter = int(time.time() // 30).to_bytes(8, 'big')
	digest = hmac.new(key, counter, hashlib.sha1).digest()
	offset = digest[-1] & 0x0F
	code = int.from_bytes(digest[offset : offset + 4], 'big') & 0x7FFFFFFF
	return f'{code % 1_000_000:06d}'


def github_device_code(account: dict) -> str:
	single = (os.getenv('ANYROUTER_GITHUB_DEVICE_CODE') or os.getenv('GITHUB_DEVICE_CODE', '')).strip()
	if single:
		return single

	raw = (os.getenv('ANYROUTER_GITHUB_DEVICE_CODES') or os.getenv('GITHUB_DEVICE_CODES', '')).strip()
	if not raw:
		return ''

	try:
		mapping = json.loads(raw)
	except Exception:
		mapping = {}
		for item in raw.split(','):
			if '=' in item:
				key, value = item.split('=', 1)
			elif ':' in item:
				key, value = item.split(':', 1)
			else:
				continue
			mapping[key.strip()] = value.strip()

	for key in (account.get('name'), account.get('github_username')):
		if key and str(mapping.get(key, '')).strip():
			return str(mapping[key]).strip()
	return ''


async def safe_click_authorize(page) -> str:
	return await page.evaluate(
		"""() => {
			const blocked = /cancel|deny|decline|return|back|取消|拒绝|返回/i;
			const allowed = /authorize|authorise|allow|approve|授权|允许|同意/i;
			const visible = (el) => {
				if (!el || !el.isConnected) return false;
				const style = window.getComputedStyle(el);
				if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
				const rect = el.getBoundingClientRect();
				return rect.width > 0 && rect.height > 0;
			};
			for (const selector of [
				'button[name="authorize"][value="1"]',
				'input[name="authorize"][value="1"]',
				'#js-oauth-authorize-btn'
			]) {
				const el = document.querySelector(selector);
				if (visible(el) && !el.disabled) {
					const label = `${el.innerText || ''} ${el.value || ''}`.trim();
					if (!blocked.test(label)) {
						el.click();
						return selector;
					}
				}
			}
			for (const el of document.querySelectorAll('button, input[type="submit"], input[type="button"]')) {
				if (!visible(el) || el.disabled) continue;
				const label = `${el.innerText || ''} ${el.value || ''} ${el.name || ''}`.trim();
				if (blocked.test(label)) continue;
				if (allowed.test(label) || (el.name === 'authorize' && el.value === '1')) {
					el.click();
					return label || el.id || el.name || 'authorize';
				}
			}
			return '';
		}"""
	)


async def switch_to_totp(page) -> None:
	await page.evaluate(
		"""() => {
			const keywords = /authenticator|totp|another way|other method|verification code|use your|authentication app|另一种方式|验证码/i;
			for (const el of document.querySelectorAll('a, button')) {
				const text = (el.textContent || '').trim();
				if (keywords.test(text)) {
					el.click();
					return true;
				}
			}
			return false;
		}"""
	)
	await page.wait_for_timeout(1500)


async def page_summary(page) -> str:
	return await page.evaluate(
		"""() => document.body.innerText
			.split("\\n")
			.map((line) => line.trim())
			.filter(Boolean)
			.slice(0, 8)
			.join(" | ")"""
	)


async def fill_totp_if_needed(page, account: dict) -> None:
	totp_selectors = [
		'#app_totp',
		'#totp',
		'input[name="app_totp"]',
		'input[name="totp"]',
	]
	generic_code_selectors = [
		'input[name="otp"]',
		'input[autocomplete="one-time-code"]',
		'input[type="text"][inputmode="numeric"]',
		'input[type="number"]',
		'input[inputmode="numeric"]',
	]

	field = None
	for selector in totp_selectors:
		field = await page.query_selector(selector)
		if field:
			break

	if not field and ('two-factor' in page.url or '2fa' in page.url):
		await switch_to_totp(page)
		for selector in totp_selectors + generic_code_selectors:
			field = await page.query_selector(selector)
			if field:
				break

	if not field:
		for selector in generic_code_selectors:
			field = await page.query_selector(selector)
			if field:
				break

	if not field:
		return

	detail = await page_summary(page)
	is_device_verification = 'sessions/verified-device' in page.url or 'Device verification' in detail

	if is_device_verification:
		code = github_device_code(account)
		if not code:
			raise RuntimeError(f'GitHub device verification code is required at {scrub_url(page.url)}: {detail[:300]}')
		print(f'  - filled GitHub device verification code for {mask_username(account["github_username"])}')
	else:
		code = generate_totp(account.get('totp_secret', ''))
		if not code:
			raise RuntimeError(f'GitHub TOTP is required at {scrub_url(page.url)}: {detail[:300]}')
		print(f'  - generated TOTP for {mask_username(account["github_username"])}')

	old_url = page.url
	await field.fill(code)
	try:
		await page.wait_for_url(lambda url: url != old_url, timeout=15000)
	except Exception:
		pass
	await page.wait_for_timeout(3000)


async def wait_for_settle(page, timeout: int = 10000) -> None:
	try:
		await page.wait_for_load_state('domcontentloaded', timeout=timeout)
	except Exception:
		pass
	await page.wait_for_timeout(1000)


async def goto_document(page, url: str):
	response = await page.goto(url, wait_until='commit', timeout=45000)
	await wait_for_settle(page)
	return response


async def browser_json(page, path: str, method: str = 'GET', headers: dict | None = None) -> dict:
	last = None
	for _ in range(8):
		result = await page.evaluate(
			"""async ({path, method, headers}) => {
				const response = await fetch(path, {
					method,
					headers: headers || {},
					credentials: "same-origin"
				});
				const text = await response.text();
				let data = null;
				try {
					data = JSON.parse(text);
				} catch (_) {}
				return {
					status: response.status,
					contentType: response.headers.get("content-type") || "",
					data,
					sample: text.slice(0, 160)
				};
			}""",
			{'path': path, 'method': method, 'headers': headers or {}},
		)
		last = result
		if result.get('data') is not None:
			return result
		await page.wait_for_timeout(3000)

	raise RuntimeError(
		f'{scrub_url(path)} did not return JSON: status={last.get("status") if last else "unknown"} '
		f'type={last.get("contentType") if last else "unknown"} sample={last.get("sample") if last else ""!r}'
	)


async def get_oauth_data(page) -> dict:
	await goto_document(page, f'{PROVIDER_ORIGIN}/login')
	await page.wait_for_timeout(6000)
	status = await browser_json(page, '/api/status')
	state = await browser_json(page, '/api/oauth/state')
	return {'client_id': status['data']['data']['github_client_id'], 'state': state['data']['data']}


async def check_account(playwright, account: dict, index: int) -> bool:
	name = account.get('name') or f'account-{index + 1}'
	username = account['github_username']
	password = account['github_password']
	STORAGE_DIR.mkdir(parents=True, exist_ok=True)
	state_path = STORAGE_DIR / f'github_{hashlib.sha256(username.encode()).hexdigest()[:12]}.json'

	print(f'[{name}] start GitHub OAuth ({mask_username(username)})')

	launch = {
		'headless': os.getenv('CHECKIN_HEADLESS', 'true').lower() in {'1', 'true', 'yes', 'on'},
		'args': [
			'--no-sandbox',
			'--disable-setuid-sandbox',
			'--ignore-certificate-errors',
			'--disable-blink-features=AutomationControlled',
		],
	}
	browser = await playwright.chromium.launch(**launch)
	context_kwargs = {'ignore_https_errors': True, 'locale': 'zh-CN', 'viewport': {'width': 1920, 'height': 1080}}
	if state_path.exists():
		context_kwargs['storage_state'] = load_github_storage_state(state_path)
		print(f'[{name}] restored GitHub storage state')

	context = await browser.new_context(**context_kwargs)
	page = await context.new_page()
	callback_urls: list[str] = []

	async def capture_oauth_callback(route):
		url = route.request.url
		if oauth_query(url):
			callback_urls.append(url)
			print(f'[{name}] captured OAuth callback: {scrub_url(url)}')
			if route.request.resource_type in {'fetch', 'xhr'}:
				await route.fulfill(
					status=200,
					content_type='application/json; charset=utf-8',
					body='{"success":false,"message":"OAuth callback captured by check-in script"}',
				)
				return
			await route.fulfill(
				status=200,
				content_type='text/html; charset=utf-8',
				body='<html><body>OAuth callback captured.</body></html>',
			)
			return
		await route.continue_()

	def remember_url(url: str) -> None:
		if oauth_query(url):
			callback_urls.append(url)

	page.on('request', lambda request: remember_url(request.url))
	page.on('framenavigated', lambda frame: remember_url(frame.url))

	try:
		oauth_data = await get_oauth_data(page)
		await context.route(f'{PROVIDER_ORIGIN}/**', capture_oauth_callback)
		oauth_url = 'https://github.com/login/oauth/authorize?' + urlencode(
			{
				'response_type': 'code',
				'client_id': oauth_data['client_id'],
				'state': oauth_data['state'],
				'scope': 'user:email',
			}
		)
		await goto_document(page, oauth_url)

		login_field = await page.query_selector('#login_field')
		if login_field:
			print(f'[{name}] filling GitHub login')
			await login_field.fill(username)
			await page.fill('#password', password)
			await page.click('input[name="commit"], input[type="submit"][value="Sign in"]')
			await wait_for_settle(page, timeout=15000)

		await fill_totp_if_needed(page, account)

		if 'github.com/login/oauth/authorize' in page.url:
			try:
				clicked = await safe_click_authorize(page)
			except Exception as exc:
				if 'Execution context was destroyed' not in str(exc):
					raise
				clicked = 'navigation'
			print(f'[{name}] authorize click: {clicked or "not needed"}')
			if clicked:
				await wait_for_settle(page, timeout=15000)

		for _ in range(60):
			remember_url(page.url)
			if callback_urls:
				break
			await page.wait_for_timeout(1000)
		await page.wait_for_timeout(3000)

		print(f'[{name}] final url: {scrub_url(page.url)}')
		query = oauth_query(callback_urls[-1]) if callback_urls else oauth_query(page.url)
		if not query:
			print(f'[{name}] OAuth callback code not found')
			return False

		await context.unroute(f'{PROVIDER_ORIGIN}/**', capture_oauth_callback)
		callback_path = f'/api/oauth/github?{urlencode(query, doseq=True)}'
		callback = await browser_json(page, callback_path, headers={'Accept': 'application/json, text/plain, */*'})
		callback_data = callback['data']
		print(
			f"[{name}] oauth api: {{'status': {callback['status']}, "
			f"'success': {callback_data.get('success')}, 'has_data': {bool(callback_data.get('data'))}}}"
		)
		if callback['status'] != 200 or not callback_data.get('success'):
			print(
				f'[{name}] oauth callback failed: {callback_data.get("message") or callback_data.get("msg") or "unknown"}'
			)
			return False

		api_user = str(callback_data.get('data', {}).get('id') or '')
		if not api_user:
			print(f'[{name}] api user missing from callback')
			return False

		headers = {
			'Accept': 'application/json, text/plain, */*',
			'Origin': PROVIDER_ORIGIN,
			'Referer': PROVIDER_ORIGIN,
			'new-api-user': api_user,
		}
		user_resp = await browser_json(page, '/api/user/self', headers=headers)
		user_data = user_resp['data']
		print(
			f"[{name}] user/self: {{'status': {user_resp['status']}, "
			f"'success': {user_data.get('success')}, 'has_data': {bool(user_data.get('data'))}}}"
		)
		if user_resp['status'] != 200 or not user_data.get('success'):
			return False

		sign_headers = {**headers, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
		sign_resp = await browser_json(page, '/api/user/sign_in', method='POST', headers=sign_headers)
		sign = sign_resp['data']
		print(
			f"[{name}] sign_in: {{'status': {sign_resp['status']}, "
			f"'success': {sign.get('success')}, 'ret': {sign.get('ret')}, 'code': {sign.get('code')}, "
			f"'message': {sign.get('message') or sign.get('msg') or ''!r}}}"
		)
		ok = sign_resp['status'] == 200 and (
			sign.get('success') is True
			or sign.get('ret') == 1
			or sign.get('code') == 0
			or '已' in (sign.get('message') or sign.get('msg') or '')
		)
		if ok:
			state_path.write_text(
				json.dumps(github_only_storage_state(await context.storage_state())), encoding='utf-8'
			)
			state_path.chmod(0o600)
			print(f'[{name}] success')
		return ok
	except Exception as exc:
		print(f'[{name}] failed: {exc}')
		return False
	finally:
		await context.close()
		await browser.close()


async def main() -> int:
	accounts = load_accounts()
	only = {item.strip() for item in os.getenv('ACCOUNT_ONLY', '').split(',') if item.strip()}
	if only:
		accounts = [
			account for account in accounts if account.get('name') in only or account.get('github_username') in only
		]
		if not accounts:
			print('summary: success=0, failed=0')
			print('no accounts matched ACCOUNT_ONLY')
			return 1
	elif os.getenv('ACCOUNT_ORDERED', '').lower() not in {'1', 'true', 'yes', 'on'}:
		random.shuffle(accounts)
		print('account order randomized')

	limit = int(os.getenv('ACCOUNT_LIMIT', str(len(accounts))))
	no_delay = '--no-delay' in sys.argv
	success = 0
	failed = 0

	if not no_delay and START_DELAY_MAX_SECONDS > 0:
		start_delay = random.randint(0, START_DELAY_MAX_SECONDS)
		print(f'startup random delay: {start_delay}s')
		await asyncio.sleep(start_delay)

	async with async_playwright() as playwright:
		for index, account in enumerate(accounts[:limit]):
			if index > 0 and not no_delay:
				delay = random.randint(ACCOUNT_DELAY_MIN_SECONDS, ACCOUNT_DELAY_MAX_SECONDS)
				print(f'delay before next account: {delay}s')
				await asyncio.sleep(delay)
			ok = await check_account(playwright, account, index)
			if ok:
				success += 1
			else:
				failed += 1

	print(f'summary: success={success}, failed={failed}')
	return 0 if success > 0 and failed == 0 else 1


if __name__ == '__main__':
	raise SystemExit(asyncio.run(main()))
