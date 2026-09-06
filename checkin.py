#!/usr/bin/env python3
"""
AnyRouter.top 自动签到脚本
"""

import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if hasattr(sys.stdout, 'reconfigure'):
	sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
	sys.stderr.reconfigure(line_buffering=True)

import httpx
from cloakbrowser import launch_async
from dotenv import load_dotenv

from utils.browser import (
	BrowserLoginResult,
	has_session_cookie,
	is_logged_in,
	launch_login_context,
	load_browser_login_settings,
	login_with_email_form,
	navigate_login_page,
	prepare_browser_page,
	read_auth_session,
	request_in_page,
	reset_turnstile_in_page,
	save_login_screenshot,
	solve_turnstile_in_page,
	take_pending_screenshots,
	verify_browser_login,
	wait_for_cookies,
	wait_for_waf_ready,
)
from utils.config import AccountConfig, AppConfig, load_accounts_config
from utils.debug import debug_print, is_debug_enabled
from utils.notify import notify
from utils.proxy import get_playwright_proxy, get_proxy_server

load_dotenv()

BALANCE_HASH_FILE = 'balance_hash.txt'
CAPTCHA_MAX_ATTEMPTS = 4
CHECK_IN_ERROR_KEY = 'check_in_error'
DEFAULT_CHECK_IN_TIMEZONE = 'Asia/Shanghai'
GOROUTER_TURNSTILE_ATTEMPTS = 3
GOROUTER_TURNSTILE_RETRY_DELAY_SECONDS = 8
XIAOBAI_MAX_REQUEST_ATTEMPTS = 3
XIAOBAI_RETRY_STATUS_CODES = (502, 503, 504)
CAPTCHA_RETRY_KEYWORDS = ('验证码', 'captcha', '过期', 'expired', 'invalid code')
ALREADY_CHECKED_KEYWORDS = (
	'已经签到',
	'已签到',
	'重复签到',
	'already checked',
	'already signed',
	'already claimed',
)


def format_check_in_time(now: datetime | None = None) -> str:
	"""按配置时区格式化执行时间，默认使用北京时间。"""
	timezone_name = os.getenv('CHECKIN_TIMEZONE', DEFAULT_CHECK_IN_TIMEZONE).strip() or DEFAULT_CHECK_IN_TIMEZONE
	try:
		timezone = ZoneInfo(timezone_name)
	except ZoneInfoNotFoundError:
		print(f'[WARN] Unknown CHECKIN_TIMEZONE "{timezone_name}", falling back to {DEFAULT_CHECK_IN_TIMEZONE}')
		timezone = ZoneInfo(DEFAULT_CHECK_IN_TIMEZONE)

	if now is None:
		now = datetime.now(timezone)
	elif now.tzinfo is None:
		now = now.replace(tzinfo=timezone)
	else:
		now = now.astimezone(timezone)
	return now.strftime('%Y-%m-%d %H:%M:%S')


def should_notify_every_run() -> bool:
	"""是否无条件发送每次签到汇总，默认开启。"""
	value = os.getenv('NOTIFY_EVERY_RUN', 'true').strip().lower()
	return value not in {'0', 'false', 'no', 'off'}


def attach_check_in_error(user_info: dict | None, error: str | None) -> dict | None:
	"""把签到接口错误附到用户信息上，避免查询余额成功后覆盖真实失败原因。"""
	if not error:
		return user_info
	result = dict(user_info) if user_info else {'success': False}
	result[CHECK_IN_ERROR_KEY] = error
	return result


def resolve_check_in_error(user_info_before: dict | None, user_info_after: dict | None) -> str:
	"""优先返回签到接口错误，再回退到前后用户信息查询错误。"""
	for user_info in (user_info_after, user_info_before):
		if not user_info:
			continue
		error = user_info.get(CHECK_IN_ERROR_KEY) or user_info.get('error')
		if error:
			return str(error)
	return 'Unknown error'


def load_balance_hash():
	"""加载余额hash"""
	try:
		if os.path.exists(BALANCE_HASH_FILE):
			with open(BALANCE_HASH_FILE, 'r', encoding='utf-8') as f:
				return f.read().strip()
	except Exception:  # nosec B110
		pass
	return None


def save_balance_hash(balance_hash):
	"""保存余额hash"""
	try:
		with open(BALANCE_HASH_FILE, 'w', encoding='utf-8') as f:
			f.write(balance_hash)
	except Exception as e:
		print(f'Warning: Failed to save balance hash: {e}')


def generate_balance_hash(balances):
	"""生成余额数据的hash"""
	simple_balances = (
		{k: {'quota': v.get('quota'), 'used': v.get('used')} for k, v in balances.items()} if balances else {}
	)
	balance_json = json.dumps(simple_balances, sort_keys=True, separators=(',', ':'))
	return hashlib.sha256(balance_json.encode('utf-8')).hexdigest()[:16]


def parse_cookies(cookies_data):
	"""解析 cookies 数据"""
	if isinstance(cookies_data, dict):
		return cookies_data

	if isinstance(cookies_data, str):
		cookies_data = cookies_data.strip()
		if cookies_data.lower().startswith('cookie:'):
			cookies_data = cookies_data.split(':', 1)[1].strip()
		cookies_dict = {}
		for cookie in cookies_data.split(';'):
			if '=' in cookie:
				key, value = cookie.strip().split('=', 1)
				cookies_dict[key] = value
		return cookies_dict
	return {}


async def get_waf_cookies_with_browser(
	account_name: str,
	login_url: str,
	required_cookies: list[str],
	*,
	use_proxy: bool = False,
):
	"""使用浏览器获取 WAF cookies"""
	print(f'[PROCESSING] {account_name}: Starting browser to get WAF cookies...')

	launch_kwargs: dict = {'headless': True}
	proxy = get_playwright_proxy(use_proxy=use_proxy)
	if proxy:
		launch_kwargs['proxy'] = proxy
	browser = await launch_async(**launch_kwargs)

	try:
		page = await browser.new_page()
		await prepare_browser_page(page)
		print(f'[PROCESSING] {account_name}: Access login page to get initial cookies...')

		await page.goto(login_url, wait_until='domcontentloaded')
		await wait_for_waf_ready(page)

		# Cloudflare 的 cf_clearance 在挑战通过后才下发，比 DOM 就绪晚 1-2 秒，
		# 直接读会拿到空集合，所以先轮询等待。
		await wait_for_cookies(page, required_cookies)

		cookies = await page.context.cookies()

		waf_cookies = {}
		for cookie in cookies:
			cookie_name = cookie.get('name')
			cookie_value = cookie.get('value')
			if cookie_name in required_cookies and cookie_value is not None:
				waf_cookies[cookie_name] = cookie_value

		print(f'[INFO] {account_name}: Got {len(waf_cookies)} WAF cookies')

		missing_cookies = [c for c in required_cookies if c not in waf_cookies]

		if missing_cookies:
			print(f'[FAILED] {account_name}: Missing WAF cookies: {missing_cookies}')
			await browser.close()
			return None

		print(f'[SUCCESS] {account_name}: Successfully got all WAF cookies')
		await browser.close()
		return waf_cookies

	except Exception as e:
		print(f'[FAILED] {account_name}: Error occurred while getting WAF cookies: {e}')
		await browser.close()
		return None


async def login_with_credentials(
	account_name: str,
	provider_config,
	provider_name: str,
	email: str,
	password: str,
	*,
	keep_open: bool = False,
) -> BrowserLoginResult | None:
	"""使用邮箱密码通过浏览器登录，返回 cookies 与拦截到的 api user id。

	keep_open=True 时登录成功后不关闭浏览器，把 context/page 一起放进返回值，
	供 request_in_page 直接在同一个已登录页面里发请求，省掉第二次开浏览器 +
	重新过 WAF 的开销（清酒就是在第二次 goto 上超时的）。
	"""
	print(f'[PROCESSING] {account_name}: Logging in with email/password...')

	login_url = f'{provider_config.domain}{provider_config.login_path}'
	settings = load_browser_login_settings(
		account_name,
		provider_name,
		persist_profile=provider_config.persist_profile,
	)
	timeout_ms = settings.wait_timeout_ms

	debug_print(
		f'[INFO] {account_name}: Browser profile={settings.profile_dir}, '
		f'persist={settings.persist_profile}, headless={settings.headless}, '
		f'humanize={settings.humanize}, timeout={timeout_ms}ms'
	)

	print(
		f'[INFO] {account_name}: Provider proxy={"enabled" if provider_config.use_proxy else "disabled"} '
		f'({provider_name})'
	)

	try:
		context = await launch_login_context(settings, use_proxy=provider_config.use_proxy)
	except Exception as e:
		print(f'[FAILED] {account_name}: Browser launch failed: {e}')
		return None

	page = None
	try:
		page = await context.new_page()
		await prepare_browser_page(page)
		await navigate_login_page(
			page,
			login_url,
			timeout_ms,
			provider=provider_name,
			account_name=account_name,
		)

		if not await is_logged_in(page):
			if await has_session_cookie(page):
				print(f'[WARN] {account_name}: Stale session cookie on login page, forcing email login')
			await save_login_screenshot(page, provider_name, account_name, 'before-email-login')
			await login_with_email_form(
				page,
				email,
				password,
				timeout_ms,
				provider=provider_name,
				account_name=account_name,
			)
		else:
			print(f'[INFO] {account_name}: Browser profile already logged in')

		console_url = f'{provider_config.domain}/console'
		user_profile = await verify_browser_login(page, console_url, timeout_ms)
		if not user_profile:
			cookies = await context.cookies()
			cookie_names = [c.get('name') for c in cookies if c.get('name')]
			print(f'[FAILED] {account_name}: Login failed - /api/user/self not verified')
			debug_print(f'[INFO] {account_name}: Current URL: {page.url}')
			debug_print(f'[INFO] {account_name}: Got cookies: {cookie_names}')
			await save_login_screenshot(page, provider_name, account_name, 'not-authenticated')
			await context.close()
			return None

		cookies = await context.cookies()
		all_cookies = {
			cookie.get('name'): cookie.get('value') for cookie in cookies if cookie.get('name') and cookie.get('value')
		}
		api_user = str(user_profile['id']) if user_profile.get('id') is not None else None
		access_token, session_id = await read_auth_session(page)

		success_msg = f'[SUCCESS] {account_name}: Login successful, got {len(all_cookies)} cookies'
		if access_token:
			success_msg += ', got access_token'
		if is_debug_enabled() and api_user:
			success_msg += f', api_user={api_user}'
		print(success_msg)
		if keep_open:
			return BrowserLoginResult(
				cookies=all_cookies,
				api_user=api_user,
				access_token=access_token,
				session_id=session_id,
				context=context,
				page=page,
			)
		await context.close()
		return BrowserLoginResult(
			cookies=all_cookies,
			api_user=api_user,
			access_token=access_token,
			session_id=session_id,
		)

	except Exception as e:
		print(f'[FAILED] {account_name}: Error during login: {e}')
		if page is not None:
			await save_login_screenshot(page, provider_name, account_name, 'login-error')
		await context.close()
		return None


def refresh_access_token(
	client,
	headers: dict,
	provider_config,
	account_name: str,
	*,
	session_id: str | None = None,
) -> str | None:
	"""用 HttpOnly 的 refresh cookie 换一枚新的 access_token。

	新版 NewAPI 的 access_token 只有分钟级有效期，靠 ``new_api_refresh``
	cookie 轮换。截图或 localStorage 里复制出来的 token 很快就过期，所以
	401 之后先尝试轮换，再判定账号失效。

	前端轮换时会带上 ``X-Auth-Session``（会话 sid）；服务端用它校验轮换请求
	与当前会话是否匹配，所以拿得到 sid 就一并送出。
	"""
	if not provider_config.auth_refresh_path:
		return None

	refresh_url = f'{provider_config.domain}{provider_config.auth_refresh_path}'
	refresh_headers = {k: v for k, v in headers.items() if k != 'Authorization'}
	refresh_headers['X-Requested-With'] = 'XMLHttpRequest'
	if session_id:
		refresh_headers['X-Auth-Session'] = session_id

	try:
		response = client.post(refresh_url, headers=refresh_headers, timeout=30)
	except Exception as e:
		debug_print(f'[WARN] {account_name}: Token refresh request failed: {e}')
		return None

	if response.status_code != 200:
		debug_print(f'[WARN] {account_name}: Token refresh returned HTTP {response.status_code}')
		return None

	try:
		payload = response.json()
	except json.JSONDecodeError:
		debug_print(f'[WARN] {account_name}: Token refresh returned non-JSON body')
		return None

	data = payload.get('data') if isinstance(payload, dict) else None
	if not isinstance(data, dict):
		return None

	token = data.get('access_token')
	if isinstance(token, str) and token:
		print(f'[INFO] {account_name}: Refreshed access_token via {provider_config.auth_refresh_path}')
		return token
	return None


NEWAPI_QUOTA_PER_UNIT = 500000


def newapi_quota_pair(info: dict) -> tuple[float, float]:
	"""把 NewAPI 的原始额度换算成展示单位，返回 (余额, 已用)。

	部分 NewAPI 分支（如 Gemai / 哈基米）把充值额度放 ``quota``、赠送额度放
	``gift_quota``，站点钱包展示的是两者之和（即 ``total_quota``）。只读
	``quota`` 会把 243 元的余额报成 0.14 元；更糟的是签到奖励若落在赠送额度
	里，前后差值恒为 0，通知会被误判成「签到无变化」。没有 ``gift_quota``
	的站点该字段缺省为 0，行为与原来一致。
	"""
	quota = _number(info.get('quota'))
	gift_quota = _number(info.get('gift_quota'))
	used_quota = _number(info.get('used_quota'))
	return (
		round((quota + gift_quota) / NEWAPI_QUOTA_PER_UNIT, 2),
		round(used_quota / NEWAPI_QUOTA_PER_UNIT, 2),
	)


def get_user_info(client, headers, user_info_url: str, *, api_user_key: str | None = None):
	"""获取用户信息。

	AnyRouter 的 ``/api/user/self`` 偶尔会因为 ``new-api-user`` 过期或 WAF
	刚刷新而返回 401，但同一组 session 仍然可以正常签到。先按浏览器请求
	补上 XHR 标记；遇到 401 时再用 session-only 请求重试，避免把有效签到误报
	为账号失效。
	"""
	request_headers = {**headers, 'X-Requested-With': 'XMLHttpRequest'}
	header_variants = [request_headers]
	if api_user_key and api_user_key in request_headers:
		header_variants.append({k: v for k, v in request_headers.items() if k != api_user_key})

	last_status = None
	try:
		for attempt, variant in enumerate(header_variants):
			response = client.get(user_info_url, headers=variant, timeout=30)
			last_status = response.status_code

			if response.status_code == 200:
				data = response.json()
				if data.get('success'):
					user_data = data.get('data', {})
					quota, used_quota = newapi_quota_pair(user_data)
					return {
						'success': True,
						'quota': quota,
						'used_quota': used_quota,
						'display': f':money: Current balance: ${quota}, Used: ${used_quota}',
					}

			# 401/403 时继续尝试 session-only 头；其它错误没有必要重复请求。
			if response.status_code not in (401, 403) or attempt == len(header_variants) - 1:
				break

		return {'success': False, 'error': f'Failed to get user info: HTTP {last_status}'}
	except Exception as e:
		return {'success': False, 'error': f'Failed to get user info: {str(e)[:50]}...'}


async def prepare_cookies(account_name: str, provider_config, user_cookies: dict) -> dict | None:
	"""准备请求所需的 cookies（可能包含 WAF cookies）"""
	waf_cookies = {}

	if provider_config.needs_waf_cookies():
		login_url = f'{provider_config.domain}{provider_config.login_path}'
		waf_cookies = await get_waf_cookies_with_browser(
			account_name,
			login_url,
			provider_config.waf_cookie_names,
			use_proxy=provider_config.use_proxy,
		)
		if not waf_cookies:
			print(f'[FAILED] {account_name}: Unable to get WAF cookies')
			return None
	else:
		print(f'[INFO] {account_name}: Bypass WAF not required, using user cookies directly')

	return {**waf_cookies, **user_cookies}


def parse_check_in_result(account_name: str, status_code: int, body: str) -> tuple[bool, str | None]:
	"""解析签到响应，同时保留失败原因供通知使用。"""
	print(f'[RESPONSE] {account_name}: Response status code {status_code}')

	if status_code != 200:
		error_msg = _response_message(body)
		if any(keyword in error_msg.lower() for keyword in ALREADY_CHECKED_KEYWORDS):
			print(f'[SUCCESS] {account_name}: Already checked in today')
			return True, None
		error = f'Check-in failed - HTTP {status_code}'
		print(f'[FAILED] {account_name}: {error}')
		return False, error

	try:
		result = json.loads(body)
	except json.JSONDecodeError:
		if 'success' in body.lower():
			print(f'[SUCCESS] {account_name}: Check-in successful!')
			return True, None
		error = 'Check-in failed - Invalid response format'
		print(f'[FAILED] {account_name}: {error}')
		return False, error

	if result.get('ret') == 1 or result.get('code') == 0 or result.get('success'):
		print(f'[SUCCESS] {account_name}: Check-in successful!')
		return True, None

	error_msg = str(result.get('msg', result.get('message', 'Unknown error')))
	if any(keyword in error_msg.lower() for keyword in ALREADY_CHECKED_KEYWORDS):
		print(f'[SUCCESS] {account_name}: Already checked in today')
		return True, None

	error = f'Check-in failed - {error_msg}'
	print(f'[FAILED] {account_name}: {error}')
	return False, error


def parse_check_in_response(account_name: str, status_code: int, body: str) -> bool:
	"""兼容旧调用方，只返回签到是否成功。"""
	success, _ = parse_check_in_result(account_name, status_code, body)
	return success


def is_checked_in_status(payload: object) -> bool:
	"""兼容不同 Bearer API 的今日签到状态字段。"""
	return isinstance(payload, dict) and bool(payload.get('checked_today') or payload.get('checked_in_today'))


def _response_message(body: str) -> str:
	"""提取签到接口错误信息，兼容 JSON 和纯文本响应。"""
	try:
		payload = json.loads(body)
	except json.JSONDecodeError:
		return body.strip()

	if isinstance(payload, dict):
		return str(payload.get('message') or payload.get('msg') or payload.get('error') or body)
	return body


def execute_captcha_check_in_result(
	client, account_name: str, provider_config, headers: dict
) -> tuple[bool, str | None]:
	"""执行需要 base64Captcha 图片验证码的签到，并返回明确错误。"""
	try:
		from captcha_ocr.base64_captcha import solve_data_url
	except Exception as exc:
		error = f'CAPTCHA OCR is unavailable: {exc}'
		print(f'[FAILED] {account_name}: {error}')
		return False, error

	checkin_headers = headers.copy()
	checkin_headers.update({'Accept': 'application/json, text/plain, */*', 'X-Requested-With': 'XMLHttpRequest'})
	captcha_url = f'{provider_config.domain}{provider_config.captcha_path}'
	sign_in_url = f'{provider_config.domain}{provider_config.sign_in_path}'

	for attempt in range(1, CAPTCHA_MAX_ATTEMPTS + 1):
		try:
			captcha_response = client.get(captcha_url, headers=checkin_headers, timeout=30)
			if captcha_response.status_code != 200:
				error = f'CAPTCHA request failed - HTTP {captcha_response.status_code}'
				print(f'[FAILED] {account_name}: {error}')
				return False, error
			captcha_payload = captcha_response.json()
			captcha_data = captcha_payload.get('data', captcha_payload) if isinstance(captcha_payload, dict) else {}
			captcha_id = str(captcha_data.get('captcha_id') or '')
			image = str(captcha_data.get('image') or '')
			if not captcha_id or not image:
				error = 'CAPTCHA response has no captcha_id/image'
				print(f'[FAILED] {account_name}: {error}')
				return False, error

			result = solve_data_url(image)
			if not result.text:
				print(f'[WARN] {account_name}: CAPTCHA OCR returned no text, refreshing image')
				continue
			if not result.exact and attempt < CAPTCHA_MAX_ATTEMPTS:
				print(f'[WARN] {account_name}: CAPTCHA OCR uncertain ({result.text}), refreshing image')
				continue

			print(
				f'[NETWORK] {account_name}: Submitting CAPTCHA check-in '
				f'({attempt}/{CAPTCHA_MAX_ATTEMPTS}, exact={result.exact})'
			)
			response = client.post(
				sign_in_url,
				json={'captcha_id': captcha_id, provider_config.captcha_code_key: result.text},
				headers=checkin_headers,
				timeout=30,
			)
			body = response.text
			message = _response_message(body)
			if any(keyword in message.lower() for keyword in ALREADY_CHECKED_KEYWORDS):
				print(f'[SUCCESS] {account_name}: Already checked in today')
				return True, None
			if response.status_code == 200:
				try:
					payload = response.json()
				except json.JSONDecodeError:
					payload = None
				if isinstance(payload, dict) and (
					payload.get('success') or payload.get('code') == 0 or payload.get('ret') == 1
				):
					print(f'[SUCCESS] {account_name}: Check-in successful!')
					return True, None
			if any(keyword in message.lower() for keyword in CAPTCHA_RETRY_KEYWORDS):
				print(f'[WARN] {account_name}: CAPTCHA rejected ({message[:120]}), refreshing image')
				continue
			error = f'Check-in failed - {message[:120]}'
			print(f'[FAILED] {account_name}: {error}')
			return False, error
		except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
			print(f'[WARN] {account_name}: CAPTCHA attempt {attempt} failed - {str(exc)[:120]}')

	error = f'CAPTCHA check-in failed after {CAPTCHA_MAX_ATTEMPTS} attempts'
	print(f'[FAILED] {account_name}: {error}')
	return False, error


def execute_captcha_check_in(client, account_name: str, provider_config, headers: dict) -> bool:
	"""兼容旧调用方，只返回验证码签到是否成功。"""
	success, _ = execute_captcha_check_in_result(client, account_name, provider_config, headers)
	return success


def parse_user_info_response(status_code: int, body: str) -> dict:
	"""解析 /api/user/self 响应，提取余额。"""
	if status_code != 200:
		return {'success': False, 'error': f'Failed to get user info: HTTP {status_code}'}

	try:
		data = json.loads(body)
	except json.JSONDecodeError:
		return {'success': False, 'error': 'Failed to get user info: invalid JSON'}

	if not data.get('success'):
		return {'success': False, 'error': f'Failed to get user info: {data.get("message", "unknown")}'}

	info = data.get('data') or {}
	quota, used_quota = newapi_quota_pair(info)
	return {
		'success': True,
		'quota': quota,
		'used_quota': used_quota,
		'user_id': info.get('id'),
		'username': info.get('username'),
		'display_name': info.get('display_name'),
		'display': f':money: Current balance: ${quota}, Used: ${used_quota}',
	}


def parse_gorouter_refresh_response(status_code: int, body: str) -> tuple[str | None, str | None, str | None]:
	"""解析 GoRouter/NewAPI 的 refresh 响应，不输出任何认证值。"""
	if status_code != 200:
		return None, None, f'Auth refresh failed - HTTP {status_code}'

	try:
		payload = json.loads(body)
	except json.JSONDecodeError:
		return None, None, 'Auth refresh failed - invalid JSON'

	if not isinstance(payload, dict) or not payload.get('success'):
		message = payload.get('message', 'unknown error') if isinstance(payload, dict) else 'invalid response'
		return None, None, f'Auth refresh failed - {message}'

	data = payload.get('data')
	if not isinstance(data, dict):
		return None, None, 'Auth refresh failed - missing response data'

	access_token = data.get('access_token')
	if not isinstance(access_token, str) or not access_token:
		return None, None, 'Auth refresh failed - missing access token'

	session = data.get('session')
	session_id = session.get('sid') if isinstance(session, dict) else None
	if not isinstance(session_id, str) or not session_id:
		session_id = None
	return access_token, session_id, None


def parse_gorouter_checkin_status(status_code: int, body: str) -> tuple[bool, str | None]:
	"""读取 GoRouter 签到状态，只有嵌套 stats 标志为 true 才确认成功。"""
	if status_code != 200:
		return False, f'Check-in status failed - HTTP {status_code}'

	try:
		payload = json.loads(body)
	except json.JSONDecodeError:
		return False, 'Check-in status failed - invalid JSON'

	if not isinstance(payload, dict) or not payload.get('success'):
		message = payload.get('message', 'unknown error') if isinstance(payload, dict) else 'invalid response'
		return False, f'Check-in status failed - {message}'

	data = payload.get('data')
	stats = data.get('stats') if isinstance(data, dict) else None
	if not isinstance(stats, dict) or 'checked_in_today' not in stats:
		return False, 'Check-in status failed - missing checked_in_today'

	return stats.get('checked_in_today') is True, None


def parse_gorouter_checkin_result(status_code: int, body: str) -> tuple[bool, bool, str | None]:
	"""解析 ``POST /api/user/checkin`` 结果，返回 (成功, 需要重试 Turnstile, 错误)。

	NewAPI 的 Turnstile 中间件在校验失败时也返回 HTTP 200，只把 ``success``
	置 false 并在 message 里写 Turnstile，所以必须看 message 而不是状态码。
	"""
	try:
		payload = json.loads(body)
	except json.JSONDecodeError:
		return False, False, f'Check-in failed - HTTP {status_code} invalid JSON'

	if not isinstance(payload, dict):
		return False, False, f'Check-in failed - HTTP {status_code} invalid response'

	message = str(payload.get('message') or '')
	if payload.get('success'):
		data = payload.get('data')
		awarded = data.get('quota_awarded') if isinstance(data, dict) else None
		if isinstance(awarded, (int, float)):
			print(f'[REWARD] Check-in awarded ${round(float(awarded) / NEWAPI_QUOTA_PER_UNIT, 2)}')
		return True, False, None

	# 与前端 shouldTriggerTurnstile 一致：只有 Turnstile 相关失败才值得换 token 重试。
	if 'Turnstile' in message:
		return False, True, f'Check-in failed - {message}'
	if status_code != 200:
		return False, False, f'Check-in failed - HTTP {status_code} {message or "unknown error"}'
	return False, False, f'Check-in failed - {message or "unknown error"}'


def unwrap_api_data(payload: object) -> object:
	"""兼容直接响应与 ``{code: 0, data: ...}`` 包装。"""
	if isinstance(payload, dict) and payload.get('code') == 0 and 'data' in payload:
		return payload['data']
	return payload


def _number(value: object, default: float = 0.0) -> float:
	try:
		return float(value)  # type: ignore[arg-type]
	except (TypeError, ValueError):
		return default


def parse_sub2api_profile_response(status_code: int, body: str) -> dict:
	"""解析 Sub2API ``/api/v1/user/profile`` 响应。"""
	if status_code != 200:
		return {'success': False, 'error': f'Failed to get user info: HTTP {status_code}'}

	try:
		payload = json.loads(body)
	except json.JSONDecodeError:
		return {'success': False, 'error': 'Failed to get user info: invalid JSON'}

	if isinstance(payload, dict) and payload.get('code') not in (None, 0):
		return {'success': False, 'error': payload.get('message', 'Failed to get user info')}

	info = unwrap_api_data(payload)
	if not isinstance(info, dict):
		return {'success': False, 'error': 'Failed to get user info: invalid response data'}

	quota = round(_number(info.get('balance')), 4)
	used_quota = round(
		_number(
			info.get(
				'used_balance',
				info.get('used_quota', info.get('total_used', info.get('total_spent', 0))),
			)
		),
		4,
	)
	return {
		'success': True,
		'quota': quota,
		'used_quota': used_quota,
		'display': f':money: Current balance: ${quota:.4f}, Used: ${used_quota:.4f}',
	}


def _sub2api_token_result(response, account_name: str) -> tuple[str | None, str | None, str | None]:
	"""解析 Bearer 登录/刷新响应，并返回可用于通知的认证错误。"""
	try:
		payload = response.json()
	except json.JSONDecodeError:
		error = 'Authentication returned invalid JSON'
		print(f'[FAILED] {account_name}: {error}')
		return None, None, error

	if response.status_code != 200:
		message = payload.get('message', f'HTTP {response.status_code}') if isinstance(payload, dict) else response.text
		error = f'Authentication failed - {message}'
		print(f'[FAILED] {account_name}: {error}')
		return None, None, error

	data = unwrap_api_data(payload)
	if not isinstance(data, dict):
		error = 'Authentication response has no token data'
		print(f'[FAILED] {account_name}: {error}')
		return None, None, error
	if data.get('requires_2fa'):
		error = 'This Sub2API account requires 2FA; use refresh_token instead'
		print(f'[FAILED] {account_name}: {error}')
		return None, None, error

	access_token = data.get('access_token')
	refresh_token = data.get('refresh_token')
	access_token = access_token if isinstance(access_token, str) and access_token else None
	refresh_token = refresh_token if isinstance(refresh_token, str) and refresh_token else None
	if not access_token:
		error = 'Authentication response has no usable access token'
		print(f'[FAILED] {account_name}: {error}')
		return None, refresh_token, error
	return access_token, refresh_token, None


def _sub2api_token_from_response(response, account_name: str) -> tuple[str | None, str | None]:
	"""兼容旧调用方，只返回 access_token 和 refresh_token。"""
	access_token, refresh_token, _ = _sub2api_token_result(response, account_name)
	return access_token, refresh_token


def _sub2api_refresh_token(
	client, account_name: str, provider_config, refresh_token: str
) -> tuple[str | None, str | None, str | None]:
	if not provider_config.auth_refresh_path:
		return None, None, 'Authentication refresh path is not configured'
	response = client.post(
		f'{provider_config.domain}{provider_config.auth_refresh_path}',
		json={'refresh_token': refresh_token},
		timeout=30,
	)
	return _sub2api_token_result(response, account_name)


def _xiaobai_response_data(response, account_name: str, action: str) -> tuple[dict | None, str | None]:
	"""解析小白 Code 的 ``{ok, data}`` 响应，不把认证信息写入日志。"""
	try:
		payload = response.json()
	except json.JSONDecodeError:
		error = f'{action} returned invalid JSON'
		print(f'[FAILED] {account_name}: {error}')
		return None, error

	if response.status_code != 200:
		message = payload.get('message') if isinstance(payload, dict) else None
		error = f'{action} failed - {message or f"HTTP {response.status_code}"}'
		print(f'[FAILED] {account_name}: {error}')
		return None, error
	if isinstance(payload, dict) and payload.get('ok') is False:
		error = f'{action} failed - {payload.get("message", "unknown error")}'
		print(f'[FAILED] {account_name}: {error}')
		return None, error

	data = payload.get('data') if isinstance(payload, dict) and 'data' in payload else unwrap_api_data(payload)
	if not isinstance(data, dict):
		error = f'{action} returned invalid response data'
		print(f'[FAILED] {account_name}: {error}')
		return None, error
	return data, None


def run_xiaobai_check_in(
	account: AccountConfig,
	account_name: str,
	provider_config,
) -> tuple[bool, dict | None, dict | None]:
	"""执行小白 Code 独立签到页的 Bearer API。"""
	client_kwargs: dict = {'http2': provider_config.http2, 'timeout': 30.0}
	proxy_url = get_proxy_server(use_proxy=provider_config.use_proxy)
	if proxy_url:
		client_kwargs['proxy'] = proxy_url
	elif provider_config.use_proxy:
		print(f'[WARN] {account_name}: Provider requires proxy but CHECKIN_PROXY_URL is not set')

	headers = {
		'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
		'Accept': 'application/json',
		'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
		'Content-Type': 'application/json',
		'Referer': f'{provider_config.domain}/checkin/',
		'Origin': provider_config.domain,
	}

	try:
		with httpx.Client(headers=headers, **client_kwargs) as client:
			access_token = account.access_token
			refresh_token = account.refresh_token
			authentication_error: str | None = None

			if not access_token and refresh_token:
				print(f'[AUTH] {account_name}: Refreshing Bearer access token')
				access_token, rotated_refresh_token, authentication_error = _sub2api_refresh_token(
					client,
					account_name,
					provider_config,
					refresh_token,
				)
				refresh_token = rotated_refresh_token or refresh_token

			if not access_token:
				error = authentication_error or 'Xiaobai requires access_token or refresh_token'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

			headers['Authorization'] = f'Bearer {access_token}'

			last_authentication_error: str | None = None

			def request(method: str, url: str, *, body: dict | None = None):
				nonlocal last_authentication_error, refresh_token

				def send():
					if method == 'GET':
						return client.get(url, headers=headers, timeout=30)
					return client.post(url, headers=headers, json=body, timeout=30)

				for attempt in range(1, XIAOBAI_MAX_REQUEST_ATTEMPTS + 1):
					response = send()
					if response.status_code == 401 and refresh_token:
						new_access_token, new_refresh_token, refresh_error = _sub2api_refresh_token(
							client,
							account_name,
							provider_config,
							refresh_token,
						)
						if new_access_token:
							headers['Authorization'] = f'Bearer {new_access_token}'
							refresh_token = new_refresh_token or refresh_token
							response = send()
						elif refresh_error:
							last_authentication_error = refresh_error

					if (
						response.status_code not in XIAOBAI_RETRY_STATUS_CODES
						or attempt == XIAOBAI_MAX_REQUEST_ATTEMPTS
					):
						return response

					print(
						f'[WARN] {account_name}: {method} {url} returned HTTP {response.status_code}; '
						f'retrying ({attempt}/{XIAOBAI_MAX_REQUEST_ATTEMPTS - 1})'
					)
					time.sleep(attempt)

				raise RuntimeError('Xiaobai request retry loop ended unexpectedly')

			status_url = f'{provider_config.domain}{provider_config.check_in_status_path}'
			status_response = request('GET', status_url)
			status, status_error = _xiaobai_response_data(status_response, account_name, 'Check-in status request')
			if status is None:
				error = last_authentication_error or status_error or 'Check-in status request failed'
				return False, None, attach_check_in_error(None, error)
			if status.get('signedToday') is True:
				print(f'[SUCCESS] {account_name}: Already checked in today')
				return True, None, None

			config = status.get('config')
			if isinstance(config, dict) and config.get('enabled') is False:
				error = 'Daily check-in is currently disabled'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

			print(f'[NETWORK] {account_name}: Executing Xiaobai daily check-in')
			check_in_url = f'{provider_config.domain}{provider_config.sign_in_path}'
			check_response = request('POST', check_in_url, body={})
			result, check_in_error = _xiaobai_response_data(check_response, account_name, 'Daily check-in')
			if result is None:
				error = last_authentication_error or check_in_error or 'Daily check-in failed'
				return False, None, attach_check_in_error(None, error)

			record = result.get('record')
			result_status = result.get('status')
			success = bool(
				result.get('alreadyChecked') is True
				or isinstance(record, dict)
				or result.get('success') is True
				or result.get('code') == 0
				or (isinstance(result_status, dict) and result_status.get('signedToday') is True)
			)
			if not success:
				error = 'Daily check-in returned an unexpected response'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

			if result.get('alreadyChecked') is True:
				print(f'[SUCCESS] {account_name}: Already checked in today')
			elif isinstance(record, dict) and record.get('reward_amount') is not None:
				print(f'[SUCCESS] {account_name}: Check-in successful, reward {record["reward_amount"]}')
			else:
				print(f'[SUCCESS] {account_name}: Check-in successful!')
			return True, None, None
	except Exception as e:
		error = f'Xiaobai check-in error - {str(e)[:100]}'
		print(f'[FAILED] {account_name}: {error}')
		return False, None, attach_check_in_error(None, error)


def run_bearer_check_in(
	account: AccountConfig,
	account_name: str,
	provider_config,
) -> tuple[bool, dict | None, dict | None]:
	"""使用 Bearer API 登录、查询余额并签到。"""
	client_kwargs: dict = {'http2': provider_config.http2, 'timeout': 30.0}
	proxy_url = get_proxy_server(use_proxy=provider_config.use_proxy)
	if proxy_url:
		client_kwargs['proxy'] = proxy_url
		print(f'[INFO] {account_name}: Bearer HTTP client proxy enabled')
	elif provider_config.use_proxy:
		print(f'[WARN] {account_name}: Provider requires proxy but CHECKIN_PROXY_URL is not set')

	headers = {
		'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
		'Accept': 'application/json, text/plain, */*',
		'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
		'Content-Type': 'application/json',
		'Referer': f'{provider_config.domain}/dashboard',
		'Origin': provider_config.domain,
	}

	try:
		with httpx.Client(headers=headers, **client_kwargs) as client:
			access_token = account.access_token
			refresh_token = account.refresh_token
			authentication_error: str | None = None

			if account.has_login_credentials():
				if not provider_config.login_api_path:
					error = 'Bearer login_api_path is not configured'
					print(f'[FAILED] {account_name}: {error}')
					return False, None, attach_check_in_error(None, error)
				print(f'[AUTH] {account_name}: Logging in through Bearer email/password API')
				response = client.post(
					f'{provider_config.domain}{provider_config.login_api_path}',
					json={'email': account.email, 'password': account.password},
					headers=headers,
					timeout=30,
				)
				access_token, login_refresh_token, authentication_error = _sub2api_token_result(response, account_name)
				refresh_token = login_refresh_token or refresh_token
			elif not access_token and refresh_token:
				print(f'[AUTH] {account_name}: Refreshing Bearer access token')
				access_token, rotated_refresh_token, authentication_error = _sub2api_refresh_token(
					client,
					account_name,
					provider_config,
					refresh_token,
				)
				refresh_token = rotated_refresh_token or refresh_token

			if not access_token:
				error = authentication_error or 'No usable Bearer access token'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

			headers['Authorization'] = f'Bearer {access_token}'
			profile_url = f'{provider_config.domain}{provider_config.user_info_path}'
			status_path = provider_config.check_in_status_path or provider_config.sign_in_path
			status_url = f'{provider_config.domain}{status_path}'
			check_in_url = f'{provider_config.domain}{provider_config.sign_in_path}'

			def get_profile():
				response = client.get(profile_url, headers=headers, timeout=30)
				return response, parse_sub2api_profile_response(response.status_code, response.text)

			profile_response, user_info_before = get_profile()
			if profile_response.status_code == 401 and refresh_token:
				new_access_token, new_refresh_token, refresh_error = _sub2api_refresh_token(
					client,
					account_name,
					provider_config,
					refresh_token,
				)
				if new_access_token:
					headers['Authorization'] = f'Bearer {new_access_token}'
					refresh_token = new_refresh_token or refresh_token
					_, user_info_before = get_profile()
				elif refresh_error:
					authentication_error = refresh_error

			if not user_info_before.get('success'):
				error = authentication_error or user_info_before.get('error', 'Unable to get profile')
				print(f'[FAILED] {account_name}: {error}')
				return False, attach_check_in_error(user_info_before, error), None
			print(user_info_before['display'])

			status_response = client.get(status_url, headers=headers, timeout=30)
			status_payload = None
			try:
				status_payload = unwrap_api_data(status_response.json())
			except json.JSONDecodeError:
				pass

			check_in_error: str | None = None
			if status_response.status_code == 200 and is_checked_in_status(status_payload):
				print(f'[SUCCESS] {account_name}: Already checked in today')
				success = True
			elif (
				status_response.status_code == 200
				and isinstance(status_payload, dict)
				and status_payload.get('eligible') is False
			):
				check_in_error = 'Daily check-in is currently not eligible'
				print(f'[FAILED] {account_name}: {check_in_error}')
				success = False
			else:
				print(f'[NETWORK] {account_name}: Executing Bearer daily check-in')
				check_response = client.post(check_in_url, headers=headers, timeout=30)
				success, check_in_error = parse_check_in_result(
					account_name, check_response.status_code, check_response.text
				)

			_, user_info_after = get_profile()
			if not success:
				user_info_after = attach_check_in_error(user_info_after, check_in_error)
			return success, user_info_before, user_info_after
	except Exception as e:
		error = f'Bearer check-in error - {str(e)[:100]}'
		print(f'[FAILED] {account_name}: {error}')
		return False, None, attach_check_in_error(None, error)


def run_newapi_password_check_in(
	account: AccountConfig,
	account_name: str,
	provider_config,
) -> tuple[bool, dict | None, dict | None]:
	"""通过新版 NewAPI 登录接口执行签到，完成后注销临时会话。"""
	identifier = account.get_login_identifier()
	if not identifier or not account.password or not provider_config.login_api_path:
		return False, None, None

	client_kwargs: dict = {'http2': provider_config.http2, 'timeout': 30.0}
	proxy_url = get_proxy_server(use_proxy=provider_config.use_proxy)
	if proxy_url:
		client_kwargs['proxy'] = proxy_url
		print(f'[INFO] {account_name}: NewAPI HTTP client proxy enabled')
	elif provider_config.use_proxy:
		print(f'[WARN] {account_name}: Provider requires proxy but CHECKIN_PROXY_URL is not set')

	base_headers = {
		'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
		'Accept': 'application/json, text/plain, */*',
		'Content-Type': 'application/json',
		'Origin': provider_config.domain,
		'Referer': f'{provider_config.domain}{provider_config.login_path}',
	}

	try:
		with httpx.Client(headers=base_headers, **client_kwargs) as client:
			print(f'[AUTH] {account_name}: Logging in through NewAPI username/password API')
			response = client.post(
				f'{provider_config.domain}{provider_config.login_api_path}',
				json={'username': identifier, 'password': account.password},
				timeout=30,
			)
			if response.status_code != 200:
				error = f'Login failed - HTTP {response.status_code}'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

			payload = response.json()
			if not payload.get('success'):
				error = f'Login failed - {payload.get("message", "unknown error")}'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)
			data = payload.get('data') or {}
			if data.get('requires_2fa'):
				error = 'Login requires 2FA'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

			access_token = data.get('access_token')
			session = data.get('session') or {}
			session_id = session.get('sid')
			user = data.get('user') or {}
			api_user = str(user.get('id')) if user.get('id') is not None else None
			if not access_token:
				error = 'Login response did not include access token'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

			headers = {**base_headers, 'Authorization': f'Bearer {access_token}'}
			if api_user and provider_config.api_user_key:
				headers[provider_config.api_user_key] = api_user
			user_info_url = f'{provider_config.domain}{provider_config.user_info_path}'
			user_info_before = get_user_info(
				client,
				headers,
				user_info_url,
				api_user_key=provider_config.api_user_key,
			)
			if not user_info_before.get('success'):
				print(f'[FAILED] {account_name}: {user_info_before.get("error", "Unable to get profile")}')
				return False, user_info_before, None
			print(user_info_before['display'])

			success, check_in_error = execute_check_in_result(client, account_name, provider_config, headers)
			user_info_after = get_user_info(
				client,
				headers,
				user_info_url,
				api_user_key=provider_config.api_user_key,
			)

			logout_headers = headers.copy()
			if session_id:
				logout_headers['X-Auth-Session'] = session_id
			try:
				client.post(
					f'{provider_config.domain}/api/user/auth/logout',
					headers=logout_headers,
					timeout=15,
				)
			except Exception:
				debug_print(f'[WARN] {account_name}: Failed to close temporary login session')
			if not success:
				user_info_after = attach_check_in_error(user_info_after, check_in_error)
			return success, user_info_before, user_info_after
	except Exception as e:
		error = f'NewAPI password check-in error - {str(e)[:100]}'
		print(f'[FAILED] {account_name}: {error}')
		return False, None, attach_check_in_error(None, error)


def execute_check_in_result(client, account_name: str, provider_config, headers: dict) -> tuple[bool, str | None]:
	"""执行签到请求并保留失败原因。"""
	if provider_config.checkin_captcha:
		return execute_captcha_check_in_result(client, account_name, provider_config, headers)

	print(f'[NETWORK] {account_name}: Executing check-in')

	checkin_headers = headers.copy()
	checkin_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
	header_variants = [checkin_headers]
	if provider_config.api_user_key in checkin_headers:
		header_variants.append({k: v for k, v in checkin_headers.items() if k != provider_config.api_user_key})

	sign_in_url = f'{provider_config.domain}{provider_config.sign_in_path}'
	for attempt, variant in enumerate(header_variants):
		response = client.post(sign_in_url, headers=variant, timeout=30)

		# 与用户信息接口保持一致：new-api-user 失效时，退回到 session-only 请求。
		if response.status_code in (401, 403) and attempt < len(header_variants) - 1:
			continue

		return parse_check_in_result(account_name, response.status_code, response.text)

	return False, 'Check-in failed after all header variants'


def execute_check_in(client, account_name: str, provider_config, headers: dict) -> bool:
	"""兼容旧调用方，只返回签到是否成功。"""
	success, _ = execute_check_in_result(client, account_name, provider_config, headers)
	return success


def format_check_in_notification(detail: dict) -> str:
	"""格式化带余额与变化的单个账号通知。"""
	name = detail['name']
	quota = detail['after_quota']
	reward = detail['check_in_reward']
	usage = detail['usage_increase']
	success = detail.get('success', True)
	icon = '✅' if success else '❌'
	parts = [f'{icon} {name}｜余额 ${quota:.2f}']

	if not success:
		parts.append('签到失败')
	elif reward > 0:
		parts.append(f'签到 +${reward:.2f}')
	else:
		parts.append('签到无变化')
	if usage > 0:
		parts.append(f'消耗 ${usage:.2f}')

	return '｜'.join(parts)


def _gorouter_status_path(provider_config, month: str) -> str:
	status_path = provider_config.check_in_status_path or provider_config.sign_in_path
	separator = '&' if '?' in status_path else '?'
	return f'{status_path}{separator}month={month}'


async def run_gorouter_check_in_in_page(
	account: AccountConfig,
	account_name: str,
	provider_config,
	*,
	api_user_override: str | None = None,
	access_token_override: str | None = None,
) -> tuple[bool, dict | None, dict | None]:
	"""使用 GoRouter 官方页面的 Turnstile 流程执行签到。

	凭据优先用 access_token（NewAPI 的 PAT，不过期、无 session 绑定）；只有在
	没有 PAT 时才退回 ``new_api_refresh`` cookie —— 后者每次刷新都会轮换，重放
	超过 30 秒宽限期会连带吊销整个会话族，所以用持久化 Profile 保存轮换结果。
	签到走 ``POST /api/user/checkin?turnstile=<token>``，token 由运行器自己渲染
	同一个 sitekey 取得，不依赖站点签到卡片的弹窗。结果只认服务端
	``checked_in_today``。
	"""
	print(f'[PROCESSING] {account_name}: Starting browser for GoRouter check-in...')
	settings = load_browser_login_settings(
		account_name,
		provider_config.name,
		persist_profile=provider_config.persist_profile,
	)
	context = None

	try:
		context = await launch_login_context(settings, use_proxy=provider_config.use_proxy)
		page = await context.new_page()
		await prepare_browser_page(page)

		user_cookies = parse_cookies(account.cookies) if account.cookies else {}
		refresh_cookie = user_cookies.get('new_api_refresh')
		if not isinstance(refresh_cookie, str) or not refresh_cookie:
			refresh_cookie = None

		access_token = access_token_override or account.access_token
		session_id = account.session_id
		# PAT 是不过期的凭据，有它就完全不用碰会轮换的 refresh cookie。
		use_refresh_flow = not access_token

		context_cookies = await context.cookies()
		has_persisted_refresh = any(
			cookie.get('name') == 'new_api_refresh' and cookie.get('value') for cookie in context_cookies
		)
		if not use_refresh_flow:
			print(f'[AUTH] {account_name}: Using access token from account configuration')
		elif refresh_cookie and not has_persisted_refresh:
			domain = provider_config.domain.split('://', 1)[-1].split('/', 1)[0]
			await context.add_cookies(
				[
					{
						'name': 'new_api_refresh',
						'value': refresh_cookie,
						'domain': domain,
						'path': '/api/user/auth',
						'httpOnly': True,
						'secure': True,
					}
				]
			)
			print(f'[AUTH] {account_name}: Loaded refresh cookie from account configuration')
		elif has_persisted_refresh:
			print(f'[AUTH] {account_name}: Reusing refresh cookie from browser profile')
		else:
			print(f'[WARN] {account_name}: No refresh cookie found in account or browser profile')

		login_url = f'{provider_config.domain}{provider_config.login_path}'
		await page.goto(login_url, wait_until='domcontentloaded', timeout=settings.wait_timeout_ms)
		await wait_for_waf_ready(page, settings.wait_timeout_ms)

		headers = {
			'Accept': 'application/json, text/plain, */*',
			'Content-Type': 'application/json',
			'X-Requested-With': 'XMLHttpRequest',
		}

		if use_refresh_flow and (has_persisted_refresh or refresh_cookie):
			refresh_status, refresh_body = await request_in_page(
				page,
				provider_config.auth_refresh_path,
				method='POST',
				headers=headers,
			)
			access_token, refreshed_session_id, refresh_error = parse_gorouter_refresh_response(
				refresh_status,
				refresh_body,
			)
			session_id = refreshed_session_id or session_id
			if not access_token and refresh_cookie and has_persisted_refresh:
				# A stale cache must not permanently hide a still-valid Secret cookie.
				domain = provider_config.domain.split('://', 1)[-1].split('/', 1)[0]
				await context.add_cookies(
					[
						{
							'name': 'new_api_refresh',
							'value': refresh_cookie,
							'domain': domain,
							'path': '/api/user/auth',
							'httpOnly': True,
							'secure': True,
						}
					]
				)
				refresh_status, refresh_body = await request_in_page(
					page,
					provider_config.auth_refresh_path,
					method='POST',
					headers=headers,
				)
				access_token, refreshed_session_id, refresh_error = parse_gorouter_refresh_response(
					refresh_status,
					refresh_body,
				)
				session_id = refreshed_session_id or session_id
			if not access_token:
				error = refresh_error or 'No usable GoRouter access token'
				print(f'[FAILED] {account_name}: {error}')
				return False, None, attach_check_in_error(None, error)

		if not access_token:
			error = 'GoRouter requires new_api_refresh or access_token'
			print(f'[FAILED] {account_name}: {error}')
			return False, None, attach_check_in_error(None, error)

		headers['Authorization'] = f'Bearer {access_token}'
		if session_id:
			headers['X-Auth-Session'] = session_id

		# 部分站点（如老魔公益站）除 Bearer 外还强制要求 New-Api-User，缺失时
		# 一律返回 401 "New-Api-User header not provided"。
		api_user = api_user_override or account.api_user
		if api_user and provider_config.api_user_key:
			headers[provider_config.api_user_key] = api_user

		status, body = await request_in_page(page, provider_config.user_info_path, headers=headers)
		user_info_before = parse_user_info_response(status, body)
		if not user_info_before.get('success'):
			error = user_info_before.get('error', 'Unable to verify GoRouter identity')
			print(f'[FAILED] {account_name}: {error}')
			return False, user_info_before, attach_check_in_error(None, error)

		identity = user_info_before.get('display_name') or user_info_before.get('username')
		identity_suffix = f' ({identity})' if identity else ''
		print(f'[SUCCESS] {account_name}: GoRouter identity verified{identity_suffix}')
		print(user_info_before['display'])

		month = datetime.now(ZoneInfo(DEFAULT_CHECK_IN_TIMEZONE)).strftime('%Y-%m')
		status_path = _gorouter_status_path(provider_config, month)
		status, body = await request_in_page(page, status_path, headers=headers)
		checked_today, status_error = parse_gorouter_checkin_status(status, body)
		if status_error:
			print(f'[FAILED] {account_name}: {status_error}')
			return False, user_info_before, attach_check_in_error(user_info_before, status_error)

		if checked_today:
			print(f'[SUCCESS] {account_name}: Already checked in today')
			status, body = await request_in_page(page, provider_config.user_info_path, headers=headers)
			return True, user_info_before, parse_user_info_response(status, body)

		sign_in_path = provider_config.sign_in_path or provider_config.check_in_status_path
		last_error = None
		for attempt in range(1, GOROUTER_TURNSTILE_ATTEMPTS + 1):
			if attempt > 1:
				# 连续在同一页面铸 token 会被 Cloudflare 冷处理（停在 before-interactive
				# 既不回调也不报错），重新加载页面换一个干净的挑战上下文再试。
				await asyncio.sleep(GOROUTER_TURNSTILE_RETRY_DELAY_SECONDS)
				try:
					await page.reload(wait_until='domcontentloaded', timeout=settings.wait_timeout_ms)
					await wait_for_waf_ready(page, settings.wait_timeout_ms)
				except Exception as exc:
					debug_print(f'[WARN] {account_name}: Page reload before retry failed: {str(exc)[:80]}')

			token, turnstile_error = await solve_turnstile_in_page(page, provider_config.turnstile_site_key)
			if not token:
				last_error = turnstile_error or 'Turnstile token was not obtained'
				print(f'[WARN] {account_name}: {last_error} (attempt {attempt}/{GOROUTER_TURNSTILE_ATTEMPTS})')
				await reset_turnstile_in_page(page)
				continue

			print(f'[NETWORK] {account_name}: Turnstile token minted, submitting check-in')
			separator = '&' if '?' in sign_in_path else '?'
			status, body = await request_in_page(
				page,
				f'{sign_in_path}{separator}turnstile={quote(token, safe="")}',
				method='POST',
				headers=headers,
			)
			await reset_turnstile_in_page(page)
			succeeded, retry_turnstile, checkin_error = parse_gorouter_checkin_result(status, body)
			if not succeeded:
				last_error = checkin_error
				already_checked = any(keyword in (checkin_error or '') for keyword in ALREADY_CHECKED_KEYWORDS)
				if retry_turnstile and attempt < GOROUTER_TURNSTILE_ATTEMPTS:
					print(f'[WARN] {account_name}: {checkin_error}, retrying with a fresh token')
					continue
				if not already_checked:
					print(f'[FAILED] {account_name}: {checkin_error}')
					return False, user_info_before, attach_check_in_error(user_info_before, checkin_error)

			# 服务端 checked_in_today 是唯一的成功判据，POST 的返回值只用于诊断。
			status, body = await request_in_page(page, status_path, headers=headers)
			checked_today, status_error = parse_gorouter_checkin_status(status, body)
			if checked_today:
				print(f'[SUCCESS] {account_name}: Check-in confirmed by checked_in_today')
				status, body = await request_in_page(page, provider_config.user_info_path, headers=headers)
				return True, user_info_before, parse_user_info_response(status, body)
			last_error = status_error or last_error or 'Check-in was not reflected by checked_in_today'
			print(f'[WARN] {account_name}: {last_error} (attempt {attempt}/{GOROUTER_TURNSTILE_ATTEMPTS})')

		error = last_error or 'GoRouter check-in was not confirmed'
		print(f'[FAILED] {account_name}: {error}')
		return False, user_info_before, attach_check_in_error(user_info_before, error)

	except Exception as e:
		error = f'Error during GoRouter check-in: {str(e)[:100]}'
		print(f'[FAILED] {account_name}: {error}')
		return False, None, attach_check_in_error(None, error)
	finally:
		if context is not None:
			await context.close()


async def run_check_in_in_page(
	account: AccountConfig,
	account_name: str,
	provider_config,
	*,
	cookies_override: dict | None = None,
	api_user_override: str | None = None,
	access_token_override: str | None = None,
	page=None,
) -> tuple[bool, dict | None, dict | None]:
	"""在浏览器页面内完成查询与签到。

	机房 IP 上 Cloudflare 会校验 TLS(JA3)/HTTP2 指纹，Python 侧的 httpx 过不去；
	由页面自己发 fetch，指纹与挑战通过时一致，凭据也直接复用页面 cookie。

	传入 page（刚刚完成邮箱密码登录的那个页面）时直接复用，不再开第二个浏览器、
	不再 goto 登录页重新过 WAF —— 这一步以前是 30s 超时的主要来源。此时 page 的
	生命周期由调用方负责关闭。
	"""
	reuse_page = page is not None
	browser = None

	if reuse_page:
		print(f'[PROCESSING] {account_name}: Reusing logged-in page for in-page requests...')
	else:
		print(f'[PROCESSING] {account_name}: Starting browser for in-page requests...')
		launch_kwargs: dict = {'headless': True}
		proxy = get_playwright_proxy(use_proxy=provider_config.use_proxy)
		if proxy:
			launch_kwargs['proxy'] = proxy
		browser = await launch_async(**launch_kwargs)

	try:
		if not reuse_page:
			settings = load_browser_login_settings(
				account_name,
				provider_config.name,
				persist_profile=provider_config.persist_profile,
			)
			timeout_ms = settings.wait_timeout_ms
			page = await browser.new_page()
			await prepare_browser_page(page)
			login_url = f'{provider_config.domain}{provider_config.login_path}'
			await page.goto(login_url, wait_until='domcontentloaded', timeout=timeout_ms)
			await wait_for_waf_ready(page, timeout_ms)
			await wait_for_cookies(page, provider_config.waf_cookie_names or [])

			# When email/password login was performed just before this function, the
			# authenticated cookies live in ``cookies_override`` rather than in the
			# original account configuration.  Reuse them in the browser context so
			# providers whose Python client stalls can still use the browser network
			# stack without losing the login session.
			user_cookies = cookies_override or (parse_cookies(account.cookies) if account.cookies else {})
			if user_cookies:
				# WAF cookies are tied to the runner's current IP/browser fingerprint. Keep the
				# fresh values obtained above instead of overwriting them with cookies copied
				# from the user's local browser.
				waf_cookie_names = set(provider_config.waf_cookie_names or [])
				user_cookies = {name: value for name, value in user_cookies.items() if name not in waf_cookie_names}
				domain = provider_config.domain.split('://', 1)[-1]
				await page.context.add_cookies(
					[
						{'name': name, 'value': value, 'domain': domain, 'path': '/'}
						for name, value in user_cookies.items()
					]
				)

		headers = {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
		api_user = api_user_override or account.api_user
		if api_user:
			headers[provider_config.api_user_key] = api_user
		access_token = access_token_override or account.access_token
		if access_token:
			headers['Authorization'] = f'Bearer {access_token}'

		status, body = await request_in_page(page, provider_config.user_info_path, headers=headers)
		user_info_before = parse_user_info_response(status, body)
		if user_info_before.get('success'):
			print(user_info_before['display'])
		else:
			print(f'[WARN] {account_name}: {user_info_before.get("error")}')
			if status in (401, 403):
				error = (
					f'Authentication failed - HTTP {status}; session cookie may be expired. '
					'Update the cookie or configure username/password for automatic login.'
				)
				print(f'[FAILED] {account_name}: {error}')
				return False, user_info_before, attach_check_in_error(user_info_before, error)

		success = True
		check_in_error: str | None = None
		if provider_config.needs_manual_check_in():
			print(f'[NETWORK] {account_name}: Executing check-in')
			status, body = await request_in_page(
				page,
				provider_config.sign_in_path,
				method='POST',
				headers=headers,
			)
			success, check_in_error = parse_check_in_result(account_name, status, body)

		status, body = await request_in_page(page, provider_config.user_info_path, headers=headers)
		user_info_after = parse_user_info_response(status, body)

		if not provider_config.needs_manual_check_in():
			success = user_info_after.get('success', False)
			if success:
				print(f'[INFO] {account_name}: Check-in completed automatically (triggered by user info request)')
			else:
				check_in_error = user_info_after.get('error', 'Auto check-in failed')

		if not success:
			user_info_after = attach_check_in_error(user_info_after, check_in_error)

		return success, user_info_before, user_info_after

	except Exception as e:
		error = f'Error during in-page check-in: {str(e)[:100]}'
		print(f'[FAILED] {account_name}: {error}')
		return False, None, attach_check_in_error(None, error)
	finally:
		# 复用外部传入的 page 时不关浏览器，交回调用方统一释放。
		if browser is not None:
			await browser.close()


async def check_in_account(account: AccountConfig, account_index: int, app_config: AppConfig):
	"""为单个账号执行签到操作"""
	account_name = account.get_display_name(account_index)
	print(f'\n[PROCESSING] Starting to process {account_name}')

	provider_config = app_config.get_provider(account.provider)
	if not provider_config:
		error = f'Provider "{account.provider}" not found in configuration'
		print(f'[FAILED] {account_name}: {error}')
		return False, None, attach_check_in_error(None, error)

	print(f'[INFO] {account_name}: Using provider "{account.provider}" ({provider_config.domain})')

	if provider_config.checkin_turnstile:
		return await run_gorouter_check_in_in_page(account, account_name, provider_config)

	if provider_config.api_style == 'xiaobai':
		return run_xiaobai_check_in(account, account_name, provider_config)
	if provider_config.api_style in ('sub2api', 'tokenrouter'):
		return run_bearer_check_in(account, account_name, provider_config)
	if provider_config.login_api_path and account.has_login_credentials():
		return run_newapi_password_check_in(account, account_name, provider_config)

	# 邮箱密码优先
	all_cookies = None
	resolved_api_user: str | None = None
	resolved_access_token: str | None = None
	resolved_session_id: str | None = None
	auth_method = None
	login_context = None
	login_page = None
	if account.has_login_credentials():
		print(f'[INFO] {account_name}: Attempting email/password login (priority)...')
		login_identifier = account.get_login_identifier()
		assert login_identifier is not None and account.password is not None
		login_result = await login_with_credentials(
			account_name,
			provider_config,
			account.provider,
			login_identifier,
			account.password,
			# 页内请求的 provider 直接复用登录页面，避免再开一个浏览器重新过 WAF。
			keep_open=bool(provider_config.request_in_page),
		)
		if login_result:
			all_cookies = login_result.cookies
			resolved_api_user = login_result.api_user
			resolved_access_token = login_result.access_token
			resolved_session_id = login_result.session_id
			login_context = login_result.context
			login_page = login_result.page
			auth_method = 'email/password'
			if resolved_access_token:
				auth_method = 'email/password + bearer token'
		else:
			error = 'Email/password login failed; stale session cookies were not used'
			print(f'[FAILED] {account_name}: {error}')
			return False, None, attach_check_in_error(None, error)
	else:
		user_cookies = parse_cookies(account.cookies) if account.cookies else {}
		if not user_cookies and not account.has_access_token():
			error = 'Invalid account configuration: missing cookies/access_token'
			print(f'[FAILED] {account_name}: {error}')
			return False, None, attach_check_in_error(None, error)
		# request_in_page 会在自己的浏览器上下文里拿 WAF cookie，这里不必再开一次。
		if provider_config.request_in_page:
			all_cookies = user_cookies
		else:
			all_cookies = (
				await prepare_cookies(account_name, provider_config, user_cookies)
				if user_cookies or provider_config.needs_waf_cookies()
				else {}
			)
		auth_method = 'bearer token' if account.has_access_token() else 'session cookies'

	try:
		if not all_cookies and not account.has_access_token():
			error = 'Unable to prepare authentication cookies'
			return False, None, attach_check_in_error(None, error)

		print(f'[AUTH] {account_name}: Using auth method -> {auth_method}')

		if provider_config.request_in_page:
			return await run_check_in_in_page(
				account,
				account_name,
				provider_config,
				cookies_override=all_cookies,
				api_user_override=resolved_api_user,
				access_token_override=resolved_access_token,
				page=login_page,
			)

		return run_check_in_requests(
			all_cookies,
			account,
			account_name,
			provider_config,
			api_user_override=resolved_api_user,
			access_token_override=resolved_access_token,
			session_id_override=resolved_session_id,
			use_proxy=provider_config.use_proxy,
		)
	finally:
		# keep_open 借出的浏览器上下文在这里统一释放。
		if login_context is not None:
			await login_context.close()


def run_check_in_requests(
	all_cookies: dict,
	account: AccountConfig,
	account_name: str,
	provider_config,
	*,
	api_user_override: str | None = None,
	access_token_override: str | None = None,
	session_id_override: str | None = None,
	use_proxy: bool = False,
) -> tuple[bool, dict | None, dict | None]:
	"""执行 HTTP 签到请求（同步，避免在 async 上下文中使用阻塞 httpx）。"""
	try:
		client_kwargs: dict = {'http2': provider_config.http2, 'timeout': 30.0}
		if not provider_config.http2:
			debug_print(f'[INFO] {account_name}: HTTP/2 disabled for this provider (Cloudflare h2 fingerprinting)')
		proxy_url = get_proxy_server(use_proxy=use_proxy)
		if proxy_url:
			client_kwargs['proxy'] = proxy_url
			if is_debug_enabled():
				print(f'[INFO] {account_name}: HTTP client proxy enabled: {proxy_url}')
			else:
				print(f'[INFO] {account_name}: HTTP client proxy enabled')
		elif use_proxy:
			print(f'[WARN] {account_name}: Provider requires proxy but CHECKIN_PROXY_URL is not set')

		with httpx.Client(**client_kwargs) as client:
			client.cookies.update(all_cookies)

			headers = {
				'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				'Accept': 'application/json, text/plain, */*',
				'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
				'Referer': provider_config.domain,
				'Origin': provider_config.domain,
				'Connection': 'keep-alive',
				'Sec-Fetch-Dest': 'empty',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Site': 'same-origin',
			}

			api_user = api_user_override or account.api_user
			if api_user:
				headers[provider_config.api_user_key] = api_user
			access_token = access_token_override or account.access_token
			if access_token:
				headers['Authorization'] = f'Bearer {access_token}'

			user_info_url = f'{provider_config.domain}{provider_config.user_info_path}'
			user_info_before = get_user_info(
				client,
				headers,
				user_info_url,
				api_user_key=provider_config.api_user_key,
			)

			# access_token 是分钟级短效凭据：认证失败时先用 refresh cookie 轮换一次，
			# 再决定是否真的判账号失效。
			if user_info_before and not user_info_before.get('success'):
				refreshed = refresh_access_token(
					client,
					headers,
					provider_config,
					account_name,
					session_id=session_id_override or account.session_id,
				)
				if refreshed:
					headers['Authorization'] = f'Bearer {refreshed}'
					user_info_before = get_user_info(
						client,
						headers,
						user_info_url,
						api_user_key=provider_config.api_user_key,
					)

			if user_info_before and user_info_before.get('success'):
				print(user_info_before['display'])
			elif user_info_before:
				print(user_info_before.get('error', 'Unknown error'))
				if not access_token:
					print(
						f'[HINT] {account_name}: This site may be Bearer-only (new NewAPI). '
						'Session cookies alone cannot authenticate — configure email+password '
						'so the browser can capture access_token, or supply a fresh access_token.'
					)

			if provider_config.needs_manual_check_in():
				success, check_in_error = execute_check_in_result(client, account_name, provider_config, headers)
				user_info_after = get_user_info(
					client,
					headers,
					user_info_url,
					api_user_key=provider_config.api_user_key,
				)
				if not success:
					user_info_after = attach_check_in_error(user_info_after, check_in_error)
				return success, user_info_before, user_info_after

			user_info_after = get_user_info(
				client,
				headers,
				user_info_url,
				api_user_key=provider_config.api_user_key,
			)
			if user_info_after and user_info_after.get('success'):
				print(f'[INFO] {account_name}: Check-in completed automatically (triggered by user info request)')
				return True, user_info_before, user_info_after
			error = user_info_after.get('error', 'Unknown error') if user_info_after else 'Unknown error'
			print(f'[FAILED] {account_name}: Auto check-in failed - {error}')
			return False, user_info_before, user_info_after

	except Exception as e:
		error = f'Error occurred during check-in process - {str(e)[:100]}'
		print(f'[FAILED] {account_name}: {error}')
		return False, None, attach_check_in_error(None, error)


async def main():
	"""主函数"""
	if is_debug_enabled():
		print('[INFO] DEBUG_MODE enabled')
		proxy_server = os.getenv('CHECKIN_PROXY_URL', '').strip()
		if proxy_server:
			print(f'[INFO] Proxy endpoint available: {proxy_server} (enabled per provider use_proxy)')
		else:
			print('[INFO] CHECKIN_PROXY_URL not set; providers with use_proxy=true will run without proxy')
	else:
		print('[INFO] Debug mode disabled (set DEBUG_MODE=true to enable screenshots and verbose logs)')

	print('[SYSTEM] AnyRouter.top multi-account auto check-in script started')
	print(f'[TIME] Execution time: {format_check_in_time()}')

	app_config = AppConfig.load_from_env()
	print(f'[INFO] Loaded {len(app_config.providers)} provider configuration(s)')
	if is_debug_enabled():
		for provider_name, provider in sorted(app_config.providers.items()):
			print(
				f'[INFO] Provider "{provider_name}": use_proxy={provider.use_proxy}, '
				f'request_in_page={provider.request_in_page}'
			)

	accounts = load_accounts_config()
	if not accounts:
		error_msg = '[FAILED] Unable to load account configuration, program exits'
		print(error_msg)
		notify.push_message('AnyRouter Check-in Alert', error_msg, msg_type='text')
		sys.exit(1)

	print(f'[INFO] Found {len(accounts)} account configurations')

	last_balance_hash = load_balance_hash()

	success_count = 0
	total_count = len(accounts)
	notification_content = []
	current_balances = {}
	account_check_in_details = {}
	need_notify = False
	balance_changed = False

	for i, account in enumerate(accounts):
		account_key = f'account_{i + 1}'
		try:
			success, user_info_before, user_info_after = await check_in_account(account, i, app_config)
			if success:
				success_count += 1

			should_notify_this_account = False

			if not success:
				should_notify_this_account = True
				need_notify = True
				account_name = account.get_display_name(i)
				print(f'[NOTIFY] {account_name} failed, will send notification')

			if user_info_after and user_info_after.get('success'):
				current_quota = user_info_after['quota']
				current_used = user_info_after['used_quota']
				current_balances[account_key] = {'quota': current_quota, 'used': current_used}

				if user_info_before and user_info_before.get('success'):
					before_quota = user_info_before['quota']
					before_used = user_info_before['used_quota']
					after_quota = user_info_after['quota']
					after_used = user_info_after['used_quota']

					total_before = before_quota + before_used
					total_after = after_quota + after_used

					check_in_reward = total_after - total_before
					usage_increase = after_used - before_used
					balance_change = after_quota - before_quota

					account_check_in_details[account_key] = {
						'name': account.get_display_name(i),
						'before_quota': before_quota,
						'before_used': before_used,
						'after_quota': after_quota,
						'after_used': after_used,
						'check_in_reward': check_in_reward,
						'usage_increase': usage_increase,
						'balance_change': balance_change,
						'success': success,
					}

			if should_notify_this_account:
				account_name = account.get_display_name(i)
				if success:
					notification_content.append(f'✅ {account_name} · 今日已签到')
				else:
					error = resolve_check_in_error(user_info_before, user_info_after)
					notification_content.append(f'❌ {account_name} · {error}')

		except Exception as e:
			account_name = account.get_display_name(i)
			print(f'[FAILED] {account_name} processing exception: {e}')
			need_notify = True
			notification_content.append(f'[FAIL] {account_name} exception: {str(e)[:50]}...')

	current_balance_hash = generate_balance_hash(current_balances) if current_balances else None
	if current_balance_hash:
		if last_balance_hash is None:
			balance_changed = True
			need_notify = True
			print('[NOTIFY] First run detected, will send notification with current balances')
		elif current_balance_hash != last_balance_hash:
			balance_changed = True
			need_notify = True
			print('[NOTIFY] Balance changes detected, will send notification')
		else:
			print('[INFO] No balance changes detected')

	if current_balance_hash:
		save_balance_hash(current_balance_hash)

	notify_every_run = should_notify_every_run()
	if notify_every_run and not need_notify:
		print('[NOTIFY] No failures or balance changes, but every-run notification is enabled')
	need_notify = need_notify or notify_every_run

	if need_notify:
		failed_count = total_count - success_count
		if failed_count == 0:
			result_icon = '✅'
		elif success_count > 0:
			result_icon = '⚠️'
		else:
			result_icon = '❌'
		summary = [
			f'{result_icon} 签到结果：{success_count}/{total_count} 成功',
			f'🕘 {format_check_in_time()}',
		]
		if failed_count:
			summary.append(f'❌ 失败：{failed_count} 个')
		if notification_content:
			summary.extend(['', '❌ 失败详情', '\n'.join(notification_content)])
		balance_lines = [
			format_check_in_notification(account_check_in_details[key])
			for key in sorted(account_check_in_details, key=lambda value: int(value.split('_')[1]))
		]
		if balance_lines:
			summary.extend(['', '💰 余额明细', '\n'.join(balance_lines)])

		notify_content = '\n'.join(summary)
		screenshot_paths = take_pending_screenshots() if is_debug_enabled() else []
		if screenshot_paths:
			github_run_id = os.getenv('GITHUB_RUN_ID', '').strip()
			github_repo = os.getenv('GITHUB_REPOSITORY', '').strip()
			screenshot_hint = f'[SCREENSHOT] {len(screenshot_paths)} debug screenshot(s) saved'
			if github_run_id and github_repo:
				run_url = f'https://github.com/{github_repo}/actions/runs/{github_run_id}'
				screenshot_hint += f'. Download artifact `checkin-screenshots-{github_run_id}` from: {run_url}'
			else:
				screenshot_hint += ' to `checkin_screenshots/`'
			notify_content += f'\n\n{screenshot_hint}'

		print(notify_content)
		notify.push_message('AnyRouter Check-in Alert', notify_content, msg_type='text')
		print('[NOTIFY] Notification sent after check-in run')
	else:
		print('[INFO] All accounts successful and no balance changes detected, notification skipped')

	sys.exit(0 if success_count > 0 else 1)


def run_main():
	"""运行主函数的包装函数"""
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print('\n[WARNING] Program interrupted by user')
		sys.exit(1)
	except Exception as e:
		print(f'\n[FAILED] Error occurred during program execution: {e}')
		sys.exit(1)


if __name__ == '__main__':
	run_main()
