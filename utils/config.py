#!/usr/bin/env python3
"""
配置管理模块
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Literal


@dataclass
class ProviderConfig:
	"""Provider 配置"""

	name: str
	domain: str
	login_path: str = '/login'
	sign_in_path: str | None = '/api/user/sign_in'
	user_info_path: str = '/api/user/self'
	api_user_key: str = 'new-api-user'
	bypass_method: Literal['waf_cookies'] | None = None
	waf_cookie_names: List[str] | None = None
	use_proxy: bool = False
	persist_profile: bool = False
	login_method: Literal['browser', 'api'] = 'browser'
	login_api_path: str = '/api/user/login'
	check_in_status_path: str | None = None
	# cookie: 旧版 NewAPI，靠 session cookie + new-api-user
	# bearer: 新版仪表盘只认 Authorization: Bearer <access_token>
	auth_style: Literal['cookie', 'bearer'] = 'cookie'
	verify_path: str = '/console'
	currency_symbol: str = '$'
	# True 时签到 POST 走 TurnstileCheck 中间件，必须带 ?turnstile=
	turnstile_required: bool = False

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
		default_turnstile_required = defaults.turnstile_required if defaults else False
		return cls(
			name=name,
			domain=data['domain'],
			login_path=data.get('login_path', defaults.login_path if defaults else '/login'),
			sign_in_path=data.get('sign_in_path', defaults.sign_in_path if defaults else '/api/user/sign_in'),
			user_info_path=data.get('user_info_path', defaults.user_info_path if defaults else '/api/user/self'),
			api_user_key=data.get('api_user_key', defaults.api_user_key if defaults else 'new-api-user'),
			bypass_method=data.get('bypass_method', defaults.bypass_method if defaults else None),
			waf_cookie_names=data.get('waf_cookie_names', defaults.waf_cookie_names if defaults else None),
			use_proxy=data.get('use_proxy', default_use_proxy),
			persist_profile=data.get('persist_profile', default_persist_profile),
			login_method=data.get('login_method', defaults.login_method if defaults else 'browser'),
			login_api_path=data.get('login_api_path', defaults.login_api_path if defaults else '/api/user/login'),
			check_in_status_path=data.get('check_in_status_path', defaults.check_in_status_path if defaults else None),
			auth_style=data.get('auth_style', defaults.auth_style if defaults else 'cookie'),
			verify_path=data.get('verify_path', defaults.verify_path if defaults else '/console'),
			currency_symbol=data.get('currency_symbol', defaults.currency_symbol if defaults else '$'),
			turnstile_required=data.get('turnstile_required', default_turnstile_required),
		)

	def needs_waf_cookies(self) -> bool:
		"""判断是否需要获取 WAF cookies"""
		return self.bypass_method == 'waf_cookies'

	def needs_manual_check_in(self) -> bool:
		"""判断是否需要手动调用签到接口"""
		return self.sign_in_path is not None

	def uses_api_login(self) -> bool:
		"""判断邮箱密码登录是否直接调用 JSON 接口（无需启动浏览器）"""
		return self.login_method == 'api'

	def uses_bearer_auth(self) -> bool:
		"""判断仪表盘接口是否只认 Authorization: Bearer（新版 NewAPI）"""
		return self.auth_style == 'bearer'


def _newapi_checkin_provider(
	name: str,
	domain: str,
	*,
	login_method: Literal['browser', 'api'],
	auth_style: Literal['cookie', 'bearer'],
	turnstile_required: bool,
	login_path: str,
	verify_path: str,
	currency_symbol: str = '$',
	use_proxy: bool = True,
) -> ProviderConfig:
	"""NewAPI 内置签到站点的公共默认值。"""
	return ProviderConfig(
		name=name,
		domain=domain,
		login_path=login_path,
		sign_in_path='/api/user/checkin',
		user_info_path='/api/user/self',
		api_user_key='new-api-user',
		bypass_method=None,
		waf_cookie_names=None,
		use_proxy=use_proxy,
		persist_profile=False,
		login_method=login_method,
		login_api_path='/api/user/login',
		check_in_status_path='/api/user/checkin',
		auth_style=auth_style,
		verify_path=verify_path,
		currency_symbol=currency_symbol,
		turnstile_required=turnstile_required,
	)


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
				use_proxy=True,
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
			'sotamodel': ProviderConfig(
				name='sotamodel',
				domain='https://sotamodel.net',
				login_path='/sign-in',
				# 签到入口在 /agents 页面底部（Daily Check-in），对应 sota-agent-checkin 接口
				sign_in_path='/api/user/sota-agent-checkin',
				user_info_path='/api/user/self',
				api_user_key='new-api-user',
				bypass_method=None,  # 站点为纯 nginx，无 WAF 验证
				waf_cookie_names=None,
				use_proxy=True,
				persist_profile=False,
				# 前端是 React + Tailwind，与 Semi Design 选择器不兼容，直接走 JSON 登录接口
				login_method='api',
				login_api_path='/api/user/login',
				# 同一路径 GET 返回 checked_in_today，比匹配多语言提示更可靠
				check_in_status_path='/api/user/sota-agent-checkin',
			),
			# 经典 Semi 前端 + 未开启 Turnstile，JSON 登录即可
			'helpcoder': _newapi_checkin_provider(
				'helpcoder',
				'https://helpcoder.cc',
				login_method='api',
				auth_style='cookie',
				turnstile_required=False,
				login_path='/login',
				verify_path='/console',
			),
			# 新仪表盘 + Turnstile，浏览器登录后用 Bearer access_token
			'seekai': _newapi_checkin_provider(
				'seekai',
				'https://seekai.cc',
				login_method='browser',
				auth_style='bearer',
				turnstile_required=True,
				login_path='/sign-in',
				verify_path='/dashboard',
			),
			'gorouter': _newapi_checkin_provider(
				'gorouter',
				'https://gorouter.app',
				login_method='browser',
				auth_style='bearer',
				turnstile_required=True,
				login_path='/sign-in',
				verify_path='/dashboard',
			),
			'justwoker': _newapi_checkin_provider(
				'justwoker',
				'https://api.justwoker.icu',
				login_method='browser',
				auth_style='bearer',
				turnstile_required=True,
				login_path='/sign-in',
				verify_path='/dashboard',
			),
			# 与 seekai 同一套前端；Cloudflare WAF 较严，非浏览器 UA 会被 403
			'tabitoken': _newapi_checkin_provider(
				'tabitoken',
				'https://tabitoken.com',
				login_method='browser',
				auth_style='bearer',
				turnstile_required=True,
				login_path='/sign-in',
				verify_path='/dashboard',
			),
			# 新仪表盘但未开启 Turnstile；额度显示为 CNY
			'hcnsec': _newapi_checkin_provider(
				'hcnsec',
				'https://api.hcnsec.cn',
				login_method='api',
				auth_style='bearer',
				turnstile_required=False,
				login_path='/sign-in',
				verify_path='/dashboard',
				currency_symbol='¥',
			),
		}

		# 尝试从环境变量加载自定义 providers
		providers_str = os.getenv('PROVIDERS')
		if providers_str:
			try:
				providers_data = json.loads(providers_str)

				if not isinstance(providers_data, dict):
					print('[WARNING] PROVIDERS must be a JSON object, ignoring custom providers')
					return cls(providers=providers)

				# 解析自定义 providers,会覆盖默认配置
				for name, provider_data in providers_data.items():
					try:
						providers[name] = ProviderConfig.from_dict(
							name,
							provider_data,
							defaults=providers.get(name),
						)
					except Exception as e:
						print(f'[WARNING] Failed to parse provider "{name}": {e}, skipping')
						continue

				print(f'[INFO] Loaded {len(providers_data)} custom provider(s) from PROVIDERS environment variable')
			except json.JSONDecodeError as e:
				print(
					f'[WARNING] Failed to parse PROVIDERS environment variable: {e}, using default configuration only'
				)
			except Exception as e:
				print(f'[WARNING] Error loading PROVIDERS: {e}, using default configuration only')

		return cls(providers=providers)

	def get_provider(self, name: str) -> ProviderConfig | None:
		"""获取指定 provider 配置"""
		return self.providers.get(name)


@dataclass
class AccountConfig:
	"""账号配置"""

	cookies: dict | str | None
	api_user: str | None = None
	provider: str = 'anyrouter'
	name: str | None = None
	email: str | None = None
	password: str | None = None
	access_token: str | None = None

	@classmethod
	def from_dict(cls, data: dict, index: int) -> 'AccountConfig':
		"""从字典创建 AccountConfig"""
		provider = data.get('provider', 'anyrouter')
		name = data.get('name', f'Account {index + 1}')

		return cls(
			cookies=data.get('cookies'),
			api_user=data.get('api_user'),
			provider=provider,
			name=name if name else None,
			email=data.get('email'),
			password=data.get('password'),
			access_token=data.get('access_token'),
		)

	def has_login_credentials(self) -> bool:
		"""是否配置了邮箱密码登录"""
		return bool(self.email and self.password)

	def get_display_name(self, index: int) -> str:
		"""获取显示名称"""
		return self.name if self.name else f'Account {index + 1}'


def load_accounts_config() -> list[AccountConfig] | None:
	"""从环境变量加载账号配置"""
	accounts_str = os.getenv('ANYROUTER_ACCOUNTS')
	if not accounts_str:
		print('ERROR: ANYROUTER_ACCOUNTS environment variable not found')
		return None

	try:
		accounts_data = json.loads(accounts_str)
	except json.JSONDecodeError as e:
		print(f'ERROR: ANYROUTER_ACCOUNTS JSON 解析失败: {e}')
		print('HINT: 常见原因 - 末尾多余逗号、使用了单引号、包含注释、或换行格式问题')
		return None

	try:
		if not isinstance(accounts_data, list):
			print('ERROR: Account configuration must use array format [{}]')
			return None

		accounts = []
		for i, account_dict in enumerate(accounts_data):
			if not isinstance(account_dict, dict):
				print(f'ERROR: Account {i + 1} configuration format is incorrect')
				return None

			if 'api_user' not in account_dict:
				has_login = account_dict.get('email') and account_dict.get('password')
				has_access_token = bool(account_dict.get('access_token'))
				if not has_login and not has_access_token:
					print(
						f'ERROR: Account {i + 1} missing required field (api_user) - '
						'only email+password or access_token login can omit it'
					)
					return None

			has_cookies = 'cookies' in account_dict and account_dict['cookies']
			has_login = account_dict.get('email') and account_dict.get('password')
			has_access_token = bool(account_dict.get('access_token'))

			if not has_cookies and not has_login and not has_access_token:
				print(f'ERROR: Account {i + 1} must have cookies, email+password, or access_token')
				return None

			if 'name' in account_dict and not account_dict['name']:
				print(f'ERROR: Account {i + 1} name field cannot be empty')
				return None

			accounts.append(AccountConfig.from_dict(account_dict, i))

		return accounts
	except Exception as e:
		print(f'ERROR: Account configuration format is incorrect: {e}')
		return None
