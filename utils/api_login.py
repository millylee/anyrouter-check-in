"""JSON 接口登录辅助函数

适用于无 WAF、无 Turnstile 且前端与 Semi Design 选择器不兼容的 NewAPI 站点
（如 sotamodel、helpcoder、hcnsec）。相比启动浏览器，直接调用 /api/user/login 更快也更稳定。

新版 NewAPI 登录成功后返回 data.access_token，后续仪表盘接口只认
Authorization: Bearer；旧版则把用户对象直接放在 data 里并种 session cookie。
两种响应都要能解析。
"""

from __future__ import annotations

import httpx

from utils.browser import BrowserLoginResult
from utils.debug import debug_print, is_debug_enabled
from utils.proxy import get_proxy_server

# 与浏览器登录共用返回类型，便于 checkin.py 统一处理
LoginResult = BrowserLoginResult

LOGIN_TIMEOUT_SECONDS = 30.0

BROWSER_LIKE_HEADERS = {
	'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
	'Accept': 'application/json, text/plain, */*',
	'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
	'Content-Type': 'application/json',
	'Cache-Control': 'no-store',
	'Sec-Fetch-Dest': 'empty',
	'Sec-Fetch-Mode': 'cors',
	'Sec-Fetch-Site': 'same-origin',
}


def _extract_user_id(payload: dict) -> str | None:
	"""从登录响应中取出用户 id，用作 new-api-user 请求头。

	旧版: data.id
	新版: data.user.id
	"""
	data = payload.get('data')
	if not isinstance(data, dict):
		return None
	user = data.get('user')
	if isinstance(user, dict) and user.get('id') is not None:
		return str(user['id'])
	if data.get('id') is not None:
		return str(data['id'])
	return None


def _extract_access_token(payload: dict) -> str | None:
	"""从新版登录包里取出仪表盘 access_token。"""
	data = payload.get('data')
	if not isinstance(data, dict):
		return None
	token = data.get('access_token')
	if isinstance(token, str) and token.strip():
		return token.strip()
	return None


def login_via_api(
	account_name: str,
	provider_config,
	email: str,
	password: str,
	*,
	use_proxy: bool = False,
) -> LoginResult | None:
	"""调用 JSON 登录接口获取 session cookies、api_user，以及可能的 access_token。

	返回 None 表示登录失败，调用方不应回退到过期的 session cookies。
	"""
	print(f'[PROCESSING] {account_name}: Logging in via JSON API...')

	login_url = f'{provider_config.domain}{provider_config.login_api_path}'
	client_kwargs: dict = {'timeout': LOGIN_TIMEOUT_SECONDS, 'follow_redirects': True}

	proxy_url = get_proxy_server(use_proxy=use_proxy)
	if proxy_url:
		client_kwargs['proxy'] = proxy_url
		print(f'[INFO] {account_name}: Login proxy enabled')
	elif use_proxy:
		print(f'[WARN] {account_name}: Provider requires proxy but CHECKIN_PROXY_URL is not set')

	headers = {**BROWSER_LIKE_HEADERS, 'Referer': f'{provider_config.domain}{provider_config.login_path}'}
	headers['Origin'] = provider_config.domain

	try:
		with httpx.Client(**client_kwargs) as client:
			# turnstile 为空表示站点未开启人机校验，接口要求该查询参数存在
			response = client.post(
				login_url,
				params={'turnstile': ''},
				headers=headers,
				json={'username': email, 'password': password},
			)

			if response.status_code != 200:
				print(f'[FAILED] {account_name}: Login failed - HTTP {response.status_code}')
				return None

			try:
				payload = response.json()
			except ValueError:
				print(f'[FAILED] {account_name}: Login failed - response is not valid JSON')
				return None

			if not payload.get('success'):
				message = payload.get('message') or payload.get('msg') or 'Unknown error'
				print(f'[FAILED] {account_name}: Login failed - {message}')
				return None

			data = payload.get('data')
			if isinstance(data, dict) and data.get('require_2fa'):
				print(
					f'[FAILED] {account_name}: Login requires two-factor authentication, '
					'which this script cannot complete automatically'
				)
				return None

			cookies = {name: value for name, value in client.cookies.items() if name and value}
			access_token = _extract_access_token(payload)
			if not cookies and not access_token:
				print(f'[FAILED] {account_name}: Login succeeded but no cookies or access_token were set')
				return None

			if getattr(provider_config, 'uses_bearer_auth', lambda: False)() and not access_token:
				print(f'[FAILED] {account_name}: Login succeeded but dashboard access_token is missing')
				return None

			api_user = _extract_user_id(payload)
			if not api_user:
				# 少数站点登录响应不带用户对象，再查一次 /api/user/self 补齐
				api_user = _fetch_api_user(client, provider_config, headers, access_token=access_token)

			success_msg = f'[SUCCESS] {account_name}: Login successful'
			if cookies:
				success_msg += f', got {len(cookies)} cookies'
			if is_debug_enabled() and api_user:
				success_msg += f', api_user={api_user}'
			if is_debug_enabled() and access_token:
				success_msg += ', access_token=yes'
			print(success_msg)
			debug_print(f'[INFO] {account_name}: Cookie names: {sorted(cookies)}')

			return LoginResult(cookies=cookies, api_user=api_user, access_token=access_token)

	except Exception as e:
		print(f'[FAILED] {account_name}: Error during API login - {str(e)[:100]}')
		return None


def _fetch_api_user(
	client: httpx.Client,
	provider_config,
	headers: dict,
	*,
	access_token: str | None = None,
) -> str | None:
	"""登录响应缺少用户 id 时，回查用户信息接口"""
	try:
		req_headers = dict(headers)
		if access_token:
			req_headers['Authorization'] = f'Bearer {access_token}'
		response = client.get(f'{provider_config.domain}{provider_config.user_info_path}', headers=req_headers)
		if response.status_code != 200:
			return None
		return _extract_user_id(response.json())
	except Exception:  # nosec B110
		return None
