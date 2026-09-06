#!/usr/bin/env python3
"""
配置管理模块
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Literal


@dataclass
class ProviderConfig:
	"""Provider 配置"""

	name: str
	domain: str
	api_style: Literal['newapi', 'sub2api', 'tokenrouter', 'xiaobai'] = 'newapi'
	login_path: str = '/login'
	login_api_path: str | None = None
	sign_in_path: str | None = '/api/user/sign_in'
	check_in_status_path: str | None = None
	user_info_path: str = '/api/user/self'
	auth_refresh_path: str | None = '/api/user/auth/refresh'
	api_user_key: str = 'new-api-user'
	bypass_method: Literal['waf_cookies'] | None = None
	waf_cookie_names: List[str] | None = None
	use_proxy: bool = False
	persist_profile: bool = False
	http2: bool = True
	request_in_page: bool = False
	checkin_captcha: bool = False
	checkin_turnstile: bool = False
	turnstile_site_key: str = ''
	captcha_path: str = '/api/captcha?scene=checkin'
	captcha_code_key: str = 'captcha_code'

	def __post_init__(self):
		required_waf_cookies = set()
		if self.waf_cookie_names and isinstance(self.waf_cookie_names, List):
			for item in self.waf_cookie_names:
				name = '' if not item or not isinstance(item, str) else item.strip()
				if not name:
					print(f'[WARNING] Found invalid WAF cookie name: {item}')
					continue

				required_waf_cookies.add(name)

		if not required_waf_cookies:
			self.bypass_method = None

		self.waf_cookie_names = list(required_waf_cookies)

	@classmethod
	def from_dict(cls, name: str, data: dict, *, defaults: 'ProviderConfig | None' = None) -> 'ProviderConfig':
		"""从字典创建 ProviderConfig

		配置格式:
		- 基础: {"domain": "https://example.com"}
		- 完整: {"domain": "https://example.com", "login_path": "/login", "use_proxy": true, ...}
		"""
		default_use_proxy = defaults.use_proxy if defaults else False
		default_persist_profile = defaults.persist_profile if defaults else False
		default_http2 = defaults.http2 if defaults else True
		default_request_in_page = defaults.request_in_page if defaults else False
		default_checkin_captcha = defaults.checkin_captcha if defaults else False
		default_checkin_turnstile = defaults.checkin_turnstile if defaults else False
		default_turnstile_site_key = defaults.turnstile_site_key if defaults else ''
		default_captcha_path = defaults.captcha_path if defaults else '/api/captcha?scene=checkin'
		default_captcha_code_key = defaults.captcha_code_key if defaults else 'captcha_code'
		return cls(
			name=name,
			domain=data['domain'],
			api_style=data.get('api_style', defaults.api_style if defaults else 'newapi'),
			login_path=data.get('login_path', defaults.login_path if defaults else '/login'),
			login_api_path=data.get('login_api_path', defaults.login_api_path if defaults else None),
			sign_in_path=data.get('sign_in_path', defaults.sign_in_path if defaults else '/api/user/sign_in'),
			check_in_status_path=data.get(
				'check_in_status_path',
				defaults.check_in_status_path if defaults else None,
			),
			user_info_path=data.get('user_info_path', defaults.user_info_path if defaults else '/api/user/self'),
			auth_refresh_path=data.get(
				'auth_refresh_path',
				defaults.auth_refresh_path if defaults else '/api/user/auth/refresh',
			),
			api_user_key=data.get('api_user_key', defaults.api_user_key if defaults else 'new-api-user'),
			bypass_method=data.get('bypass_method', defaults.bypass_method if defaults else None),
			waf_cookie_names=data.get('waf_cookie_names', defaults.waf_cookie_names if defaults else None),
			use_proxy=data.get('use_proxy', default_use_proxy),
			persist_profile=data.get('persist_profile', default_persist_profile),
			http2=data.get('http2', default_http2),
			request_in_page=data.get('request_in_page', default_request_in_page),
			checkin_captcha=data.get('checkin_captcha', default_checkin_captcha),
			checkin_turnstile=data.get('checkin_turnstile', default_checkin_turnstile),
			turnstile_site_key=data.get('turnstile_site_key', default_turnstile_site_key),
			captcha_path=data.get('captcha_path', default_captcha_path),
			captcha_code_key=data.get('captcha_code_key', default_captcha_code_key),
		)

	def needs_waf_cookies(self) -> bool:
		"""判断是否需要获取 WAF cookies"""
		return self.bypass_method == 'waf_cookies'

	def needs_manual_check_in(self) -> bool:
		"""判断是否需要手动调用签到接口"""
		return self.sign_in_path is not None


@dataclass
class AppConfig:
	"""应用配置"""

	providers: Dict[str, ProviderConfig]

	@classmethod
	def load_from_env(cls) -> 'AppConfig':
		"""从环境变量加载配置"""
		providers = {
			'anyrouter': ProviderConfig(
				name='anyrouter',
				domain='https://anyrouter.top',
				login_path='/login',
				sign_in_path='/api/user/sign_in',
				user_info_path='/api/user/self',
				api_user_key='new-api-user',
				bypass_method='waf_cookies',
				waf_cookie_names=['acw_tc', 'cdn_sec_tc', 'acw_sc__v2'],
				use_proxy=False,
				persist_profile=True,
			),
			'agentrouter': ProviderConfig(
				name='agentrouter',
				domain='https://agentrouter.org',
				login_path='/login',
				sign_in_path=None,  # 无需签到接口，查询用户信息时自动完成签到
				user_info_path='/api/user/self',
				api_user_key='new-api-user',
				bypass_method='waf_cookies',
				waf_cookie_names=['acw_tc'],
				use_proxy=True,
				persist_profile=False,
			),
			'futureppo': ProviderConfig(
				name='futureppo',
				domain='https://api.futureppo.top',
				login_path='/login',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				api_user_key='new-api-user',
				bypass_method='waf_cookies',
				waf_cookie_names=['cf_clearance'],
				use_proxy=True,
				persist_profile=False,
				# Cloudflare 会对 HTTP/2 指纹（SETTINGS 帧、伪头顺序）做校验，httpx 的
				# h2 指纹和 Chrome 不一致，即便持有有效 cf_clearance 也一律 403。
				# 走 HTTP/1.1 时只看 UA + cf_clearance，能正常通过。
				http2=False,
				# 机房 IP 上 CF 还会查 TLS(JA3) 指纹，httpx 无论怎么设都过不了，
				# 所以签到/查询一律交给浏览器页面自己发。
				request_in_page=True,
			),
			'twinkle': ProviderConfig(
				name='twinkle',
				domain='https://big-model.smart-agi.com',
				api_style='sub2api',
				login_path='/login',
				login_api_path='/api/v1/auth/login',
				sign_in_path='/api/v1/user/daily-checkin',
				user_info_path='/api/v1/user/profile',
				auth_refresh_path='/api/v1/auth/refresh',
				api_user_key='',
				use_proxy=True,
			),
			'42w': ProviderConfig(
				name='42w',
				domain='https://api.42w.shop',
				login_path='/profile',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				api_user_key='New-Api-User',
				bypass_method='waf_cookies',
				waf_cookie_names=['cf_clearance'],
				use_proxy=True,
				http2=False,
				request_in_page=True,
			),
			'kapibala': ProviderConfig(
				name='kapibala',
				domain='https://kapibala.asia',
				login_path='/profile',
				login_api_path='/api/user/login',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'qingjiu': ProviderConfig(
				name='qingjiu',
				domain='https://qingjiu.nemodesk.top',
				login_path='/login',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
				# qingjiu occasionally stalls on the Python/httpx connection after a
				# browser login. Reuse the authenticated browser network stack instead.
				http2=False,
				request_in_page=True,
			),
			'nianhua': ProviderConfig(
				name='nianhua',
				domain='https://us-3.nianhuaapi.com',
				login_path='/profile',
				login_api_path='/api/user/login',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'sheapi': ProviderConfig(
				name='sheapi',
				domain='https://www.sheapi.top',
				login_path='/profile',
				login_api_path='/api/user/login',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=True,
				checkin_captcha=True,
			),
			'aiaiai': ProviderConfig(
				name='aiaiai',
				domain='https://api.aiaiai001.com',
				login_path='/profile',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'guyscode': ProviderConfig(
				name='guyscode',
				domain='https://www.guyscode.com',
				api_style='tokenrouter',
				login_path='/login',
				login_api_path='/api/v1/auth/login',
				sign_in_path='/api/v1/check-in',
				check_in_status_path='/api/v1/check-in/status',
				user_info_path='/api/v1/auth/me',
				auth_refresh_path='/api/v1/auth/refresh',
				api_user_key='',
				use_proxy=False,
			),
			'xiaobai': ProviderConfig(
				name='xiaobai',
				domain='https://token.dialoguedui.com',
				api_style='xiaobai',
				login_path='/login',
				login_api_path='/api/v1/auth/login',
				sign_in_path='/checkin/api/checkin',
				check_in_status_path='/checkin/api/status',
				user_info_path='/api/v1/auth/me',
				auth_refresh_path='/api/v1/auth/refresh',
				api_user_key='',
				use_proxy=False,
			),
			'ciyuan': ProviderConfig(
				name='ciyuan',
				domain='https://ai.962831.xyz',
				login_path='/console/personal',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
				persist_profile=True,
				checkin_turnstile=True,
				turnstile_site_key='0x4AAAAAADub4IXwHwHzJPGa',
			),
			'yuecheng': ProviderConfig(
				name='yuecheng',
				domain='https://52ccl.net',
				login_path='/profile',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'elysiver': ProviderConfig(
				name='elysiver',
				domain='https://elysiver.h-e.top',
				login_path='/profile',
				sign_in_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'windhub': ProviderConfig(
				name='windhub',
				domain='https://windhub.cc',
				login_path='/console/personal',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'gorouter': ProviderConfig(
				name='gorouter',
				domain='https://gorouter.app',
				login_path='/console/personal',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
				persist_profile=True,
				checkin_turnstile=True,
				turnstile_site_key='0x4AAAAAAELziOpg1Y2gFtAt',
			),
			'justwoker': ProviderConfig(
				name='justwoker',
				domain='https://api.justwoker.icu',
				login_path='/console/personal',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
				persist_profile=True,
				checkin_turnstile=True,
				turnstile_site_key='0x4AAAAAAEQ0v37GMr9cC_Kw',
			),
			'tabitoken': ProviderConfig(
				name='tabitoken',
				domain='https://tabitoken.com',
				login_path='/console/personal',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
				persist_profile=True,
				checkin_turnstile=True,
				turnstile_site_key='0x4AAAAAAEGV81TArluaPQGB',
			),
			'laomo': ProviderConfig(
				name='laomo',
				domain='https://api.2020111.xyz',
				login_path='/console/personal',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
				persist_profile=True,
				checkin_turnstile=True,
				turnstile_site_key='0x4AAAAAAD5FNNbWZboF0Wzx',
			),
			'nhh123': ProviderConfig(
				name='nhh123',
				domain='https://api.123nhh.com',
				login_path='/profile',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'superapi': ProviderConfig(
				name='superapi',
				domain='https://superapi.buzz',
				login_path='/profile',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
			'gemai': ProviderConfig(
				name='gemai',
				domain='https://api.gemai.cc',
				login_path='/profile',
				sign_in_path='/api/user/checkin',
				check_in_status_path='/api/user/checkin',
				user_info_path='/api/user/self',
				auth_refresh_path='/api/user/auth/refresh',
				api_user_key='New-Api-User',
				use_proxy=False,
			),
		}

		# 依次加载主配置和追加配置。EXTRA_PROVIDERS 用于在无法读取原 Secret 时安全追加站点。
		for env_name in ('PROVIDERS', 'EXTRA_PROVIDERS'):
			providers_str = os.getenv(env_name)
			if not providers_str:
				continue

			try:
				providers_data = json.loads(providers_str)

				if not isinstance(providers_data, dict):
					print(f'[WARNING] {env_name} must be a JSON object, ignoring it')
					continue

				# 后加载的配置会覆盖同名 provider，并继承未显式填写的已有设置。
				loaded_count = 0
				for name, provider_data in providers_data.items():
					try:
						providers[name] = ProviderConfig.from_dict(
							name,
							provider_data,
							defaults=providers.get(name),
						)
						loaded_count += 1
					except Exception as e:
						print(f'[WARNING] Failed to parse provider "{name}" from {env_name}: {e}, skipping')

				print(f'[INFO] Loaded {loaded_count} custom provider(s) from {env_name} environment variable')
			except json.JSONDecodeError as e:
				print(f'[WARNING] Failed to parse {env_name} environment variable: {e}, ignoring it')
			except Exception as e:
				print(f'[WARNING] Error loading {env_name}: {e}, ignoring it')

		return cls(providers=providers)

	def get_provider(self, name: str) -> ProviderConfig | None:
		"""获取指定 provider 配置"""
		return self.providers.get(name)


@dataclass
class AccountConfig:
	"""账号配置"""

	cookies: dict | str | None
	api_user: str | None = None
	access_token: str | None = None
	refresh_token: str | None = None
	session_id: str | None = None
	provider: str = 'anyrouter'
	name: str | None = None
	username: str | None = None
	email: str | None = None
	password: str | None = None

	@classmethod
	def from_dict(cls, data: dict, index: int) -> 'AccountConfig':
		"""从字典创建 AccountConfig"""
		provider = data.get('provider', 'anyrouter')
		name = data.get('name', f'Account {index + 1}')

		return cls(
			cookies=data.get('cookies'),
			api_user=data.get('api_user'),
			access_token=data.get('access_token') or data.get('accessToken') or data.get('token'),
			refresh_token=data.get('refresh_token') or data.get('refreshToken'),
			session_id=data.get('session_id') or data.get('sid'),
			provider=provider,
			name=name if name else None,
			username=data.get('username'),
			email=data.get('email'),
			password=data.get('password'),
		)

	def has_login_credentials(self) -> bool:
		"""是否配置了邮箱密码登录"""
		return bool((self.username or self.email) and self.password)

	def get_login_identifier(self) -> str | None:
		return self.username or self.email

	def has_access_token(self) -> bool:
		"""是否配置了新版 Bearer access token"""
		return bool(self.access_token)

	def has_refresh_token(self) -> bool:
		return bool(self.refresh_token)

	def get_display_name(self, index: int) -> str:
		"""获取显示名称"""
		return self.name if self.name else f'Account {index + 1}'


def _account_env_names() -> list[str]:
	"""按加载顺序列出账号配置的环境变量名。

	``EXTRA_ACCOUNTS_2``、``EXTRA_ACCOUNTS_3``…… 让新站点可以单独占一个
	Secret：GitHub Secret 写入后无法再读出，追加新账号时若复用同一个 Secret
	就只能整体覆盖，会把别的账号覆写没了。
	"""
	numbered = sorted(
		(name for name in os.environ if re.fullmatch(r'EXTRA_ACCOUNTS_(\d+)', name)),
		key=lambda name: int(name.rsplit('_', 1)[1]),
	)
	return ['ANYROUTER_ACCOUNTS', 'EXTRA_ACCOUNTS', *numbered]


def load_accounts_config() -> list[AccountConfig] | None:
	"""从环境变量加载账号配置"""
	account_sources = []
	for env_name in _account_env_names():
		accounts_str = os.getenv(env_name)
		if not accounts_str:
			continue

		try:
			accounts_data = json.loads(accounts_str)
		except json.JSONDecodeError as e:
			print(f'ERROR: {env_name} JSON 解析失败: {e}')
			print('HINT: 常见原因 - 末尾多余逗号、使用了单引号、包含注释、或换行格式问题')
			return None

		if not isinstance(accounts_data, list):
			print(f'ERROR: {env_name} must use array format [{{}}]')
			return None

		account_sources.extend(accounts_data)
		print(f'[INFO] Loaded {len(accounts_data)} account(s) from {env_name}')

	if not account_sources:
		print('ERROR: ANYROUTER_ACCOUNTS or EXTRA_ACCOUNTS environment variable not found')
		return None

	try:
		merged_account_sources = []
		account_indexes_by_name = {}
		for account_dict in account_sources:
			if not isinstance(account_dict, dict):
				print('ERROR: Account configuration format is incorrect')
				return None

			name = account_dict.get('name')
			if name and name in account_indexes_by_name:
				merged_account_sources[account_indexes_by_name[name]] = account_dict
				continue

			if name:
				account_indexes_by_name[name] = len(merged_account_sources)
			merged_account_sources.append(account_dict)

		accounts = []
		for i, account_dict in enumerate(merged_account_sources):
			if account_dict.get('disabled') is True:
				print(f'[INFO] Account "{account_dict.get("name", i + 1)}" is disabled, skipping')
				continue

			has_access_token = bool(
				account_dict.get('access_token') or account_dict.get('accessToken') or account_dict.get('token')
			)
			has_refresh_token = bool(account_dict.get('refresh_token') or account_dict.get('refreshToken'))
			has_cookies = 'cookies' in account_dict and account_dict['cookies']
			has_login = (account_dict.get('username') or account_dict.get('email')) and account_dict.get('password')

			if 'api_user' not in account_dict:
				if not has_cookies and not has_login and not has_access_token and not has_refresh_token:
					print(
						f'ERROR: Account {i + 1} must have cookies, access_token, refresh_token, or username/email+password'
					)
					return None

			if not has_cookies and not has_login and not has_access_token and not has_refresh_token:
				print(
					f'ERROR: Account {i + 1} must have cookies, access_token, refresh_token, or username/email+password'
				)
				return None

			if 'name' in account_dict and not account_dict['name']:
				print(f'ERROR: Account {i + 1} name field cannot be empty')
				return None

			accounts.append(AccountConfig.from_dict(account_dict, i))

		return accounts
	except Exception as e:
		print(f'ERROR: Account configuration format is incorrect: {e}')
		return None
