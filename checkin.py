#!/usr/bin/env python3
"""
AnyRouter.top 自动签到脚本
"""

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
	sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
	sys.stderr.reconfigure(line_buffering=True)

import httpx
from cloakbrowser import launch_async
from dotenv import load_dotenv

from utils.api_login import login_via_api
from utils.browser import (
	AuthCapture,
	BrowserLoginResult,
	has_session_cookie,
	is_logged_in,
	launch_login_context,
	load_browser_login_settings,
	login_with_email_form,
	mint_turnstile_token,
	navigate_login_page,
	prepare_browser_page,
	save_login_screenshot,
	take_pending_screenshots,
	verify_browser_login,
	wait_for_waf_ready,
)
from utils.config import AccountConfig, AppConfig, load_accounts_config
from utils.debug import debug_print, is_debug_enabled
from utils.notify import notify
from utils.proxy import get_playwright_proxy, get_proxy_server

load_dotenv()

BALANCE_HASH_FILE = 'balance_hash.txt'


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
) -> BrowserLoginResult | None:
	"""使用邮箱密码通过浏览器登录，返回 cookies、api user id 以及可能的 access_token。"""
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
	capture: AuthCapture | None = None
	try:
		page = await context.new_page()
		await prepare_browser_page(page)
		capture = AuthCapture(page)
		capture.start()
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

		verify_path = getattr(provider_config, 'verify_path', None) or '/console'
		console_url = f'{provider_config.domain}{verify_path}'
		verified = await verify_browser_login(page, console_url, timeout_ms)
		await capture.snapshot_from_page()
		access_token = capture.access_token or verified.access_token
		user_profile = capture.user_profile or verified.profile
		if not user_profile and not access_token:
			cookies = await context.cookies()
			cookie_names = [c.get('name') for c in cookies if c.get('name')]
			print(f'[FAILED] {account_name}: Login failed - /api/user/self not verified')
			debug_print(f'[INFO] {account_name}: Current URL: {page.url}')
			debug_print(f'[INFO] {account_name}: Got cookies: {cookie_names}')
			await save_login_screenshot(page, provider_name, account_name, 'not-authenticated')
			await context.close()
			return None

		if getattr(provider_config, 'uses_bearer_auth', lambda: False)() and not access_token:
			print(f'[FAILED] {account_name}: Login succeeded but dashboard access_token is missing')
			await save_login_screenshot(page, provider_name, account_name, 'missing-access-token')
			await context.close()
			return None

		turnstile_token = None
		if getattr(provider_config, 'turnstile_required', False):
			turnstile_token = await mint_turnstile_token(page)
			if not turnstile_token:
				print(f'[WARN] {account_name}: Failed to mint a fresh Turnstile token for check-in')

		cookies = await context.cookies()
		all_cookies = {
			str(cookie['name']): str(cookie['value'])
			for cookie in cookies
			if cookie.get('name') and cookie.get('value')
		}
		api_user = None
		if user_profile and user_profile.get('id') is not None:
			api_user = str(user_profile['id'])

		success_msg = f'[SUCCESS] {account_name}: Login successful, got {len(all_cookies)} cookies'
		if is_debug_enabled() and api_user:
			success_msg += f', api_user={api_user}'
		if is_debug_enabled() and access_token:
			success_msg += ', access_token=yes'
		print(success_msg)
		await context.close()
		return BrowserLoginResult(
			cookies=all_cookies,
			api_user=api_user,
			access_token=access_token,
			turnstile_token=turnstile_token,
		)

	except Exception as e:
		print(f'[FAILED] {account_name}: Error during login: {e}')
		if page is not None:
			await save_login_screenshot(page, provider_name, account_name, 'login-error')
		await context.close()
		return None
	finally:
		if capture is not None:
			capture.stop()


def get_user_info(client, headers, user_info_url: str, *, currency_symbol: str = '$'):
	"""获取用户信息"""
	try:
		response = client.get(user_info_url, headers=headers, timeout=30)

		if response.status_code == 200:
			data = response.json()
			if data.get('success'):
				user_data = data.get('data', {})
				if isinstance(user_data, dict) and isinstance(user_data.get('user'), dict):
					user_data = user_data['user']
				quota = round(user_data.get('quota', 0) / 500000, 2)
				used_quota = round(user_data.get('used_quota', 0) / 500000, 2)
				symbol = currency_symbol or '$'
				return {
					'success': True,
					'quota': quota,
					'used_quota': used_quota,
					'currency_symbol': symbol,
					'display': f':money: Current balance: {symbol}{quota}, Used: {symbol}{used_quota}',
				}
		return {'success': False, 'error': f'Failed to get user info: HTTP {response.status_code}'}
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


ALREADY_CHECKED_IN_KEYWORDS = (
	'已经签到',
	'已签到',
	'重复签到',
	'仅可签到一次',
	'already checked',
	'already signed',
	'already claimed',
	'once per day',
	'checked in today',
)


def is_already_checked_in(message: str) -> bool:
	"""判断签到接口返回的失败信息是否其实代表“今日已签到”"""
	if not message:
		return False
	lowered = message.lower()
	return any(keyword in lowered for keyword in ALREADY_CHECKED_IN_KEYWORDS)


def flatten_check_in_status(data: dict) -> dict:
	"""把 NewAPI 嵌套的 data.stats 摊平，兼容 sotamodel 的扁平结构。"""
	flattened = dict(data)
	stats = data.get('stats')
	if isinstance(stats, dict):
		for key, value in stats.items():
			flattened.setdefault(key, value)
	return flattened


def fetch_check_in_status(client, account_name: str, provider_config, headers: dict) -> dict | None:
	"""查询签到状态。返回 None 表示该 provider 未提供状态接口或查询失败。

	相比匹配服务端返回的多语言提示，checked_in_today 布尔值更可靠。
	"""
	status_path = getattr(provider_config, 'check_in_status_path', None)
	if not status_path:
		return None

	params = {'month': datetime.now().strftime('%Y-%m')}
	try:
		response = client.get(
			f'{provider_config.domain}{status_path}',
			headers=headers,
			params=params,
			timeout=30,
		)
		if response.status_code != 200:
			debug_print(f'[INFO] {account_name}: Check-in status query returned HTTP {response.status_code}')
			return None
		payload = response.json()
	except Exception as e:
		debug_print(f'[INFO] {account_name}: Check-in status query failed: {str(e)[:80]}')
		return None

	data = payload.get('data')
	if not payload.get('success') or not isinstance(data, dict):
		debug_print(f'[INFO] {account_name}: Check-in status unavailable: {payload.get("message")}')
		return None
	return flatten_check_in_status(data)


def _needs_turnstile_retry(message: str) -> bool:
	if not message:
		return False
	lowered = message.lower()
	return 'turnstile' in lowered


def execute_check_in(
	client,
	account_name: str,
	provider_config,
	headers: dict,
	*,
	turnstile_token: str | None = None,
):
	"""执行签到请求"""
	checkin_headers = headers.copy()
	checkin_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})

	status = fetch_check_in_status(client, account_name, provider_config, checkin_headers)
	if status is not None:
		reward = status.get('reward_credits')
		if reward is None and status.get('quota_awarded') is not None:
			try:
				reward = round(float(status['quota_awarded']) / 500000, 2)
			except (TypeError, ValueError):
				reward = None
		currency = getattr(provider_config, 'currency_symbol', None) or '$'
		if reward is not None:
			print(f"[INFO] {account_name}: Today's check-in reward: {currency}{reward}")
		if status.get('checked_in_today') is True:
			print(f'[SUCCESS] {account_name}: Already checked in today, skipping check-in request')
			return True

	print(f'[NETWORK] {account_name}: Executing check-in')

	sign_in_url = f'{provider_config.domain}{provider_config.sign_in_path}'
	turnstile_required = bool(getattr(provider_config, 'turnstile_required', False))
	request_kwargs: dict = {'headers': checkin_headers, 'timeout': 30}
	if turnstile_required or turnstile_token:
		request_kwargs['params'] = {'turnstile': turnstile_token or ''}

	response = client.post(sign_in_url, **request_kwargs)

	print(f'[RESPONSE] {account_name}: Response status code {response.status_code}')

	def _interpret(response_obj) -> tuple[bool | None, str]:
		if response_obj.status_code != 200:
			return False, f'HTTP {response_obj.status_code}'
		try:
			result = response_obj.json()
			if result.get('ret') == 1 or result.get('code') == 0 or result.get('success'):
				return True, ''
			error_msg = result.get('msg', result.get('message', 'Unknown error'))
			if is_already_checked_in(error_msg):
				return True, error_msg
			return False, error_msg
		except json.JSONDecodeError:
			if 'success' in response_obj.text.lower():
				return True, ''
			return False, 'Invalid response format'

	ok, error_msg = _interpret(response)
	if ok:
		if error_msg and is_already_checked_in(error_msg):
			print(f'[SUCCESS] {account_name}: Already checked in today')
		else:
			print(f'[SUCCESS] {account_name}: Check-in successful!')
		return True

	if _needs_turnstile_retry(error_msg):
		if not turnstile_token:
			# 浏览器没领到 token，重试同样会被拒，直接给出可操作的提示
			print(
				f'[FAILED] {account_name}: Check-in requires a Turnstile token but none was obtained '
				'(check the browser login step) - '
				f'{error_msg}'
			)
			return False
		# token 是一次性的，仅在服务端校验疑似瞬时失败时重试一次
		print(f'[WARN] {account_name}: Turnstile verification failed server-side, retrying once - {error_msg}')
		response = client.post(sign_in_url, **request_kwargs)
		ok, error_msg = _interpret(response)
		if ok:
			print(f'[SUCCESS] {account_name}: Check-in successful!')
			return True

	print(f'[FAILED] {account_name}: Check-in failed - {error_msg}')
	return False


def format_check_in_notification(detail: dict) -> str:
	"""格式化签到通知消息"""
	symbol = detail.get('currency_symbol') or '$'
	lines = [
		f'[CHECK-IN] {detail["name"]}',
		'  ━━━━━━━━━━━━━━━━━━━━',
		'  签到前',
		f'     余额: {symbol}{detail["before_quota"]:.2f}  |  累计消耗: {symbol}{detail["before_used"]:.2f}',
		'  签到后',
		f'     余额: {symbol}{detail["after_quota"]:.2f}  |  累计消耗: {symbol}{detail["after_used"]:.2f}',
	]

	has_reward = detail['check_in_reward'] != 0
	has_usage = detail['usage_increase'] != 0

	if has_reward or has_usage:
		lines.append('  ━━━━━━━━━━━━━━━━━━━━')

		if not has_reward and has_usage:
			lines.append('  今日已签到（期间有使用）')

		if has_reward:
			lines.append(f'  签到获得: +{symbol}{detail["check_in_reward"]:.2f}')

		if has_usage:
			lines.append(f'  期间消耗: {symbol}{detail["usage_increase"]:.2f}')

		if detail['balance_change'] != 0:
			change_symbol = '+' if detail['balance_change'] > 0 else ''
			lines.append(f'  余额变化: {change_symbol}{symbol}{detail["balance_change"]:.2f}')
	else:
		lines.extend(['  ━━━━━━━━━━━━━━━━━━━━', '  今日已签到，无变化'])

	return '\n'.join(lines)


async def check_in_account(account: AccountConfig, account_index: int, app_config: AppConfig):
	"""为单个账号执行签到操作"""
	account_name = account.get_display_name(account_index)
	print(f'\n[PROCESSING] Starting to process {account_name}')

	provider_config = app_config.get_provider(account.provider)
	if not provider_config:
		print(f'[FAILED] {account_name}: Provider "{account.provider}" not found in configuration')
		return False, None, None

	print(f'[INFO] {account_name}: Using provider "{account.provider}" ({provider_config.domain})')

	all_cookies = None
	resolved_api_user: str | None = None
	resolved_access_token: str | None = account.access_token
	resolved_turnstile: str | None = None
	auth_method = None
	if account.has_login_credentials():
		print(f'[INFO] {account_name}: Attempting email/password login (priority)...')
		assert account.email is not None and account.password is not None
		if provider_config.uses_api_login():
			login_result = login_via_api(
				account_name,
				provider_config,
				account.email,
				account.password,
				use_proxy=provider_config.use_proxy,
			)
			auth_method = 'email/password (API)'
		else:
			login_result = await login_with_credentials(
				account_name,
				provider_config,
				account.provider,
				account.email,
				account.password,
			)
			auth_method = 'email/password'
		if login_result:
			all_cookies = login_result.cookies
			resolved_api_user = login_result.api_user
			resolved_access_token = login_result.access_token or resolved_access_token
			resolved_turnstile = login_result.turnstile_token
		else:
			print(f'[FAILED] {account_name}: Email/password login failed, will not use stale session cookies')
			return False, None, None
	elif account.access_token:
		user_cookies = parse_cookies(account.cookies) if account.cookies else {}
		all_cookies = user_cookies or {}
		resolved_api_user = account.api_user
		auth_method = 'access_token'
	else:
		user_cookies = parse_cookies(account.cookies)
		if not user_cookies:
			print(f'[FAILED] {account_name}: Invalid configuration format')
			return False, None, None
		all_cookies = await prepare_cookies(account_name, provider_config, user_cookies)
		auth_method = 'session cookies'

	if not all_cookies and not resolved_access_token:
		return False, None, None

	print(f'[AUTH] {account_name}: Using auth method -> {auth_method}')

	return run_check_in_requests(
		all_cookies or {},
		account,
		account_name,
		provider_config,
		api_user_override=resolved_api_user,
		access_token=resolved_access_token,
		turnstile_token=resolved_turnstile,
		use_proxy=provider_config.use_proxy,
	)


def run_check_in_requests(
	all_cookies: dict,
	account: AccountConfig,
	account_name: str,
	provider_config,
	*,
	api_user_override: str | None = None,
	access_token: str | None = None,
	turnstile_token: str | None = None,
	use_proxy: bool = False,
) -> tuple[bool, dict | None, dict | None]:
	"""执行 HTTP 签到请求（同步，避免在 async 上下文中使用阻塞 httpx）。"""
	try:
		client_kwargs: dict = {'http2': True, 'timeout': 30.0}
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
			if all_cookies:
				client.cookies.update(all_cookies)

			headers = {
				'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				'Accept': 'application/json, text/plain, */*',
				'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
				'Accept-Encoding': 'gzip, deflate, br, zstd',
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
			token = access_token or account.access_token
			if token:
				headers['Authorization'] = f'Bearer {token}'

			user_info_url = f'{provider_config.domain}{provider_config.user_info_path}'
			currency = getattr(provider_config, 'currency_symbol', None) or '$'
			user_info_before = get_user_info(client, headers, user_info_url, currency_symbol=currency)
			if user_info_before and user_info_before.get('success'):
				print(user_info_before['display'])
			elif user_info_before:
				print(user_info_before.get('error', 'Unknown error'))

			if provider_config.needs_manual_check_in():
				success = execute_check_in(
					client,
					account_name,
					provider_config,
					headers,
					turnstile_token=turnstile_token,
				)
				user_info_after = get_user_info(client, headers, user_info_url, currency_symbol=currency)
				return success, user_info_before, user_info_after

			user_info_after = get_user_info(client, headers, user_info_url, currency_symbol=currency)
			if user_info_after and user_info_after.get('success'):
				print(f'[INFO] {account_name}: Check-in completed automatically (triggered by user info request)')
				return True, user_info_before, user_info_after
			error = user_info_after.get('error', 'Unknown error') if user_info_after else 'Unknown error'
			print(f'[FAILED] {account_name}: Auto check-in failed - {error}')
			return False, user_info_before, user_info_after

	except Exception as e:
		print(f'[FAILED] {account_name}: Error occurred during check-in process - {str(e)[:50]}...')
		return False, None, None


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
	print(f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

	app_config = AppConfig.load_from_env()
	print(f'[INFO] Loaded {len(app_config.providers)} provider configuration(s)')
	if is_debug_enabled():
		for provider_name, provider in sorted(app_config.providers.items()):
			print(f'[INFO] Provider "{provider_name}": use_proxy={provider.use_proxy}')

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
						'currency_symbol': user_info_after.get('currency_symbol', '$'),
					}

			if should_notify_this_account:
				account_name = account.get_display_name(i)
				status = '[SUCCESS]' if success else '[FAIL]'
				account_result = f'{status} {account_name}'
				if user_info_after and user_info_after.get('success'):
					account_result += f'\n{user_info_after["display"]}'
				elif user_info_after:
					account_result += f'\n{user_info_after.get("error", "Unknown error")}'
				notification_content.append(account_result)

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

	if balance_changed:
		for i, account in enumerate(accounts):
			account_key = f'account_{i + 1}'
			if account_key in account_check_in_details:
				detail = account_check_in_details[account_key]
				account_name = detail['name']
				account_result = format_check_in_notification(detail)
				if not any(account_name in item for item in notification_content):
					notification_content.append(account_result)

	if current_balance_hash:
		save_balance_hash(current_balance_hash)

	if need_notify and notification_content:
		summary = [
			'[STATS] Check-in result statistics:',
			f'[SUCCESS] Success: {success_count}/{total_count}',
			f'[FAIL] Failed: {total_count - success_count}/{total_count}',
		]

		if success_count == total_count:
			summary.append('[SUCCESS] All accounts check-in successful!')
		elif success_count > 0:
			summary.append('[WARN] Some accounts check-in successful')
		else:
			summary.append('[ERROR] All accounts check-in failed')

		time_info = f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

		notify_content = '\n\n'.join([time_info, '\n'.join(notification_content), '\n'.join(summary)])
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
		print('[NOTIFY] Notification sent due to failures or balance changes')
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
