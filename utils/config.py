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

	def __post_init__(self):
		self.domain = self.domain.rstrip('/')

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
	def from_dict(cls, name: str, data: dict) -> 'ProviderConfig':
		"""从字典创建 ProviderConfig

		配置格式:
		- 基础: {"domain": "https://example.com"}
		- 完整: {"domain": "https://example.com", "login_path": "/login", "api_user_key": "x-api-user", "bypass_method": "waf_cookies", ...}
		"""
		return cls(
			name=name,
			domain=data['domain'],
			login_path=data.get('login_path', '/login'),
			sign_in_path=data.get('sign_in_path', '/api/user/sign_in'),
			user_info_path=data.get('user_info_path', '/api/user/self'),
			api_user_key=data.get('api_user_key', 'new-api-user'),
			bypass_method=data.get('bypass_method'),
			waf_cookie_names=data.get('waf_cookie_names'),
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
			),
		}

		# 尝试从环境变量加载自定义 providers
		providers_str = os.getenv('PROVIDERS')
		if providers_str:
			try:
				providers_data = json.loads(_normalize_json_string(providers_str))

				if not isinstance(providers_data, dict):
					print('[WARNING] PROVIDERS must be a JSON object, ignoring custom providers')
					return cls(providers=providers)

				# 解析自定义 providers,会覆盖默认配置
				for name, provider_data in providers_data.items():
					try:
						providers[name] = ProviderConfig.from_dict(name, provider_data)
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

	cookies: dict | str
	api_user: str
	provider: str = 'anyrouter'
	name: str | None = None

	@classmethod
	def from_dict(cls, data: dict, index: int) -> 'AccountConfig':
		"""从字典创建 AccountConfig"""
		provider = data.get('provider', 'anyrouter')
		name = data.get('name', f'Account {index + 1}')

		return cls(cookies=data['cookies'], api_user=data['api_user'], provider=provider, name=name if name else None)

	def get_display_name(self, index: int) -> str:
		"""获取显示名称"""
		return self.name if self.name else f'Account {index + 1}'


def _normalize_json_string(s: str) -> str:
	"""Normalize a JSON string by stripping leading/trailing whitespace per line.

	This allows multi-line JSON in environment variables / GitHub Secrets
	without needing to manually flatten to a single line.
	"""
	return ''.join(line.strip() for line in s.splitlines())


def _load_individual_accounts() -> list[dict]:
	"""Load accounts from ANYROUTER_ACCOUNT_* prefixed environment variables."""
	accounts = []
	prefix = 'ANYROUTER_ACCOUNT_'
	for key, value in sorted(os.environ.items()):
		if key.startswith(prefix) and key != 'ANYROUTER_ACCOUNTS':
			try:
				account_data = json.loads(_normalize_json_string(value))
				if isinstance(account_data, dict):
					account_data['_env_key'] = key
					accounts.append(account_data)
				else:
					print(f'[WARNING] {key} must be a JSON object, skipping')
			except json.JSONDecodeError as e:
				print(f'[WARNING] Failed to parse {key}: {e}, skipping')
	return accounts


def _merge_accounts(base_accounts: list[dict], individual_accounts: list[dict]) -> list[dict]:
	"""Merge individual accounts into base accounts.

	If an individual account's env key suffix contains the api_user of a base account,
	it will override fields in that base account (useful for updating cookies only).
	Otherwise it's appended as a new account.
	"""
	merged = [dict(a) for a in base_accounts]

	api_user_index = {}
	for idx, acct in enumerate(merged):
		au = str(acct.get('api_user', ''))
		if au:
			api_user_index[au] = idx

	for ind_acct in individual_accounts:
		env_key = ind_acct.pop('_env_key', '')
		suffix = env_key[len('ANYROUTER_ACCOUNT_') :] if env_key.startswith('ANYROUTER_ACCOUNT_') else ''

		matched_idx = None
		for api_user_val, idx in api_user_index.items():
			if api_user_val in suffix:
				matched_idx = idx
				break

		if matched_idx is not None:
			for field, value in ind_acct.items():
				merged[matched_idx][field] = value
			print(f'[INFO] {env_key}: merged into existing account (api_user match in suffix)')
		else:
			merged.append(ind_acct)
			au = str(ind_acct.get('api_user', ''))
			if au:
				api_user_index[au] = len(merged) - 1
			print(f'[INFO] {env_key}: added as new account')

	return merged


def _validate_account_dict(account_dict: dict, index: int) -> bool:
	"""Validate a single account dict has required fields."""
	if not isinstance(account_dict, dict):
		print(f'ERROR: Account {index + 1} configuration format is incorrect')
		return False
	if 'cookies' not in account_dict or 'api_user' not in account_dict:
		print(f'ERROR: Account {index + 1} missing required fields (cookies, api_user)')
		return False
	if 'name' in account_dict and not account_dict['name']:
		print(f'ERROR: Account {index + 1} name field cannot be empty')
		return False
	return True


def load_accounts_config() -> list[AccountConfig] | None:
	"""从环境变量加载账号配置。

	Supports:
	- ANYROUTER_ACCOUNTS: JSON array (single-line or multi-line)
	- ANYROUTER_ACCOUNT_*: Individual account JSON objects
	- Automatic merging: individual accounts override base accounts by api_user match
	"""
	accounts_str = os.getenv('ANYROUTER_ACCOUNTS')
	individual_accounts = _load_individual_accounts()

	if not accounts_str and not individual_accounts:
		print('ERROR: No account configuration found (ANYROUTER_ACCOUNTS or ANYROUTER_ACCOUNT_* required)')
		return None

	base_accounts: list[dict] = []
	if accounts_str:
		try:
			normalized = _normalize_json_string(accounts_str)
			accounts_data = json.loads(normalized)

			if not isinstance(accounts_data, list):
				print('ERROR: ANYROUTER_ACCOUNTS must be a JSON array [{}]')
				return None

			base_accounts = accounts_data
		except json.JSONDecodeError as e:
			print(f'ERROR: ANYROUTER_ACCOUNTS format is incorrect: {e}')
			return None

	all_accounts_data = _merge_accounts(base_accounts, individual_accounts)

	if not all_accounts_data:
		print('ERROR: No valid account configuration found after merging')
		return None

	accounts = []
	for i, account_dict in enumerate(all_accounts_data):
		if not _validate_account_dict(account_dict, i):
			return None
		accounts.append(AccountConfig.from_dict(account_dict, i))

	seen_api_users = set()
	unique_accounts = []
	for acct in accounts:
		if acct.api_user not in seen_api_users:
			seen_api_users.add(acct.api_user)
			unique_accounts.append(acct)
		else:
			print(f'[WARNING] Duplicate api_user "{acct.api_user}" detected, keeping first occurrence')

	print(f'[INFO] Loaded {len(unique_accounts)} account(s) total')
	return unique_accounts
