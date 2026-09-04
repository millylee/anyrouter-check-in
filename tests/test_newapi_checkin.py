"""NewAPI 签到站点（helpcoder / seekai / gorouter / justwoker / hcnsec）的配置与流程测试"""

import json

import httpx
import pytest

from checkin import execute_check_in, fetch_check_in_status, flatten_check_in_status, get_user_info
from utils.api_login import login_via_api
from utils.browser import extract_access_token
from utils.config import AppConfig, load_accounts_config


@pytest.fixture
def providers(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	return AppConfig.load_from_env().providers


def _client(handler, provider) -> httpx.Client:
	return httpx.Client(transport=httpx.MockTransport(handler), base_url=provider.domain)


def _login_with_client(client, provider):
	"""复用同一个 mock client 执行登录（绕过内部 Client 创建）"""
	import utils.api_login as api_login

	class _NoClose:
		def __init__(self, inner):
			self._inner = inner

		def __enter__(self):
			return self._inner

		def __exit__(self, *exc):
			return False

	original = api_login.httpx.Client
	api_login.httpx.Client = lambda **kwargs: _NoClose(client)
	try:
		return api_login.login_via_api('Test', provider, 'a@b.com', 'pw')
	finally:
		api_login.httpx.Client = original


# ---------------------------------------------------------------- provider 配置

NEWAPI_SITES = ('helpcoder', 'seekai', 'gorouter', 'justwoker', 'hcnsec', 'tabitoken')


@pytest.mark.parametrize('name', NEWAPI_SITES)
def test_newapi_sites_are_builtin(providers, name):
	provider = providers[name]
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.login_api_path == '/api/user/login'
	assert provider.needs_waf_cookies() is False
	assert provider.needs_manual_check_in() is True


@pytest.mark.parametrize(
	('name', 'domain', 'login_method', 'auth_style', 'turnstile', 'login_path', 'verify_path', 'symbol'),
	[
		('helpcoder', 'https://helpcoder.cc', 'api', 'cookie', False, '/login', '/console', '$'),
		('seekai', 'https://seekai.cc', 'browser', 'bearer', True, '/sign-in', '/dashboard', '$'),
		('gorouter', 'https://gorouter.app', 'browser', 'bearer', True, '/sign-in', '/dashboard', '$'),
		('justwoker', 'https://api.justwoker.icu', 'browser', 'bearer', True, '/sign-in', '/dashboard', '$'),
		('hcnsec', 'https://api.hcnsec.cn', 'api', 'bearer', False, '/sign-in', '/dashboard', '¥'),
		('tabitoken', 'https://tabitoken.com', 'browser', 'bearer', True, '/sign-in', '/dashboard', '$'),
	],
)
def test_newapi_site_shapes(
	providers, name, domain, login_method, auth_style, turnstile, login_path, verify_path, symbol
):
	provider = providers[name]
	assert provider.domain == domain
	assert provider.login_method == login_method
	assert provider.auth_style == auth_style
	assert provider.uses_bearer_auth() is (auth_style == 'bearer')
	assert provider.uses_api_login() is (login_method == 'api')
	assert provider.turnstile_required is turnstile
	assert provider.login_path == login_path
	assert provider.verify_path == verify_path
	assert provider.currency_symbol == symbol


def test_legacy_providers_keep_cookie_auth(providers):
	for name in ('anyrouter', 'agentrouter', 'sotamodel'):
		assert providers[name].uses_bearer_auth() is False
		assert providers[name].turnstile_required is False
		assert providers[name].verify_path == '/console'
		assert providers[name].currency_symbol == '$'


def test_newapi_fields_can_be_overridden(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps({'seekai': {'domain': 'https://mirror.example.com', 'turnstile_required': False}}),
	)

	provider = AppConfig.load_from_env().get_provider('seekai')

	assert provider.domain == 'https://mirror.example.com'
	assert provider.turnstile_required is False
	# 其余内置字段仍从默认值继承
	assert provider.auth_style == 'bearer'
	assert provider.verify_path == '/dashboard'
	assert provider.sign_in_path == '/api/user/checkin'


# ----------------------------------------------------------- 签到状态摊平与判定


def test_flatten_check_in_status_lifts_nested_stats():
	data = {
		'enabled': True,
		'min_quota': 1000,
		'stats': {'checked_in_today': True, 'total_checkins': 7, 'total_quota': 3500000},
	}

	flattened = flatten_check_in_status(data)

	assert flattened['checked_in_today'] is True
	assert flattened['total_checkins'] == 7
	assert flattened['enabled'] is True
	# 原始 stats 保留，便于调试
	assert flattened['stats']['total_quota'] == 3500000


def test_flatten_check_in_status_keeps_top_level_priority():
	data = {'checked_in_today': False, 'stats': {'checked_in_today': True}}

	assert flatten_check_in_status(data)['checked_in_today'] is False


def test_flatten_check_in_status_tolerates_missing_stats():
	assert flatten_check_in_status({'checked_in_today': True}) == {'checked_in_today': True}


def test_fetch_check_in_status_reads_nested_stats(providers):
	seen = {}

	def handler(request: httpx.Request) -> httpx.Response:
		seen['method'] = request.method
		seen['url'] = str(request.url)
		return httpx.Response(
			200,
			json={
				'success': True,
				'data': {'enabled': True, 'stats': {'checked_in_today': True, 'total_checkins': 3}},
			},
		)

	with _client(handler, providers['hcnsec']) as client:
		status = fetch_check_in_status(client, 'Test', providers['hcnsec'], {})

	assert status is not None
	assert status['checked_in_today'] is True
	assert seen['method'] == 'GET'
	# 官方前端按月拉取签到记录
	assert 'month=' in seen['url']


def test_execute_check_in_skips_post_when_nested_stats_say_checked_in(providers):
	calls = []

	def handler(request: httpx.Request) -> httpx.Response:
		calls.append(request.method)
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': True}}})
		raise AssertionError('check-in POST must be skipped')

	with _client(handler, providers['seekai']) as client:
		assert execute_check_in(client, 'Test', providers['seekai'], {}) is True

	assert calls == ['GET']


def test_execute_check_in_treats_backend_already_message_as_success(providers):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		return httpx.Response(200, json={'success': False, 'message': '今日已签到'})

	with _client(handler, providers['helpcoder']) as client:
		assert execute_check_in(client, 'Test', providers['helpcoder'], {}) is True


def test_execute_check_in_reports_quota_awarded(providers, capsys):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		return httpx.Response(
			200,
			json={
				'success': True,
				'message': '签到成功',
				'data': {'quota_awarded': 2500000, 'checkin_date': '2026-09-04'},
			},
		)

	with _client(handler, providers['helpcoder']) as client:
		assert execute_check_in(client, 'Test', providers['helpcoder'], {}) is True

	assert 'Check-in successful' in capsys.readouterr().out


# --------------------------------------------------------------- Turnstile 查询参数


def test_execute_check_in_sends_turnstile_query_when_required(providers):
	seen = {}

	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		seen['url'] = str(request.url)
		return httpx.Response(200, json={'success': True, 'data': {'quota_awarded': 1000}})

	with _client(handler, providers['gorouter']) as client:
		assert execute_check_in(client, 'Test', providers['gorouter'], {}, turnstile_token='tok-123') is True

	assert 'turnstile=tok-123' in seen['url']


def test_execute_check_in_sends_empty_turnstile_when_token_missing(providers):
	seen = {}

	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		seen['url'] = str(request.url)
		return httpx.Response(200, json={'success': True, 'data': {'quota_awarded': 1000}})

	with _client(handler, providers['justwoker']) as client:
		assert execute_check_in(client, 'Test', providers['justwoker'], {}) is True

	assert 'turnstile=' in seen['url']


def test_execute_check_in_omits_turnstile_for_sites_without_it(providers):
	seen = {}

	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		seen['url'] = str(request.url)
		return httpx.Response(200, json={'success': True, 'data': {'quota_awarded': 1000}})

	with _client(handler, providers['helpcoder']) as client:
		assert execute_check_in(client, 'Test', providers['helpcoder'], {}) is True

	assert 'turnstile' not in seen['url']


def test_execute_check_in_retries_once_on_turnstile_rejection(providers):
	posts = []

	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		posts.append(str(request.url))
		if len(posts) == 1:
			return httpx.Response(200, json={'success': False, 'message': 'Turnstile token 为空'})
		return httpx.Response(200, json={'success': True, 'data': {'quota_awarded': 1000}})

	with _client(handler, providers['seekai']) as client:
		assert execute_check_in(client, 'Test', providers['seekai'], {}, turnstile_token='tok-abc') is True

	assert len(posts) == 2


def test_execute_check_in_does_not_retry_without_token(providers, capsys):
	posts = []

	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		posts.append(request.method)
		return httpx.Response(200, json={'success': False, 'message': 'Turnstile token 为空'})

	with _client(handler, providers['seekai']) as client:
		assert execute_check_in(client, 'Test', providers['seekai'], {}) is False

	# 没有 token 时重试必然再次被拒，应直接给出可操作的提示
	assert len(posts) == 1
	assert 'none was obtained' in capsys.readouterr().out


def test_execute_check_in_stops_after_one_failed_turnstile_retry(providers):
	posts = []

	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'stats': {'checked_in_today': False}}})
		posts.append(request.method)
		return httpx.Response(200, json={'success': False, 'message': 'Turnstile 校验失败'})

	with _client(handler, providers['seekai']) as client:
		assert execute_check_in(client, 'Test', providers['seekai'], {}, turnstile_token='ts-1') is False

	assert len(posts) == 2


# ------------------------------------------------------------------ 新版登录解析


def test_login_via_api_extracts_bearer_token_and_nested_user(providers):
	seen = {}

	def handler(request: httpx.Request) -> httpx.Response:
		seen['body'] = json.loads(request.content)
		return httpx.Response(
			200,
			json={
				'success': True,
				'data': {
					'access_token': 'at-xyz',
					'token_type': 'Bearer',
					'session': 'sess-1',
					'user': {'id': 4590, 'username': 'demo'},
				},
			},
			headers={'set-cookie': 'new_api_has_session=1; Path=/'},
		)

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		result = _login_with_client(client, providers['hcnsec'])

	assert result is not None
	assert result.access_token == 'at-xyz'
	assert result.api_user == '4590'
	assert seen['body'] == {'username': 'a@b.com', 'password': 'pw'}


def test_login_via_api_rejects_bearer_site_without_access_token(providers):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(
			200,
			json={'success': True, 'data': {'user': {'id': 1}}},
			headers={'set-cookie': 'new_api_has_session=1; Path=/'},
		)

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		assert _login_with_client(client, providers['hcnsec']) is None


def test_login_via_api_accepts_cookie_site_without_access_token(providers):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(
			200,
			json={'success': True, 'data': {'id': 88, 'username': 'demo'}},
			headers={'set-cookie': 'session=sess-abc; Path=/'},
		)

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		result = _login_with_client(client, providers['helpcoder'])

	assert result is not None
	assert result.api_user == '88'
	assert result.access_token is None
	assert result.cookies['session'] == 'sess-abc'


def test_login_via_api_uses_bearer_when_falling_back_to_user_self(providers):
	seen = {}

	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == '/api/user/login':
			return httpx.Response(200, json={'success': True, 'data': {'access_token': 'at-1'}})
		seen['auth'] = request.headers.get('authorization')
		return httpx.Response(200, json={'success': True, 'data': {'user': {'id': 999}}})

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		result = _login_with_client(client, providers['hcnsec'])

	assert result is not None
	assert result.api_user == '999'
	assert seen['auth'] == 'Bearer at-1'


def test_login_via_api_handles_network_error_for_newapi_site(providers, monkeypatch):
	def boom(**kwargs):
		raise httpx.ConnectError('no route to host')

	monkeypatch.setattr(httpx, 'Client', boom)
	assert login_via_api('Test', providers['helpcoder'], 'a@b.com', 'pw') is None


@pytest.mark.parametrize(
	('payload', 'expected'),
	[
		({'data': {'access_token': 'a'}}, 'a'),
		({'access_token': 'b'}, 'b'),
		({'data': {'accessToken': 'c'}}, 'c'),
		({'data': {'user': {'access_token': 'd'}}}, 'd'),
		({'data': {'access_token': '  e  '}}, 'e'),
		({'data': {'access_token': ''}}, None),
		({'data': {'access_token': None}}, None),
		({'data': 'not-a-dict'}, None),
		({}, None),
		('nope', None),
	],
)
def test_extract_access_token(payload, expected):
	assert extract_access_token(payload) == expected


# ------------------------------------------------------------------- 额度显示


def test_get_user_info_uses_currency_symbol(providers):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={'success': True, 'data': {'quota': 5000000, 'used_quota': 500000}})

	provider = providers['hcnsec']
	with _client(handler, provider) as client:
		info = get_user_info(client, {}, f'{provider.domain}/api/user/self', currency_symbol=provider.currency_symbol)

	assert info['success'] is True
	assert info['quota'] == 10.0
	assert info['used_quota'] == 1.0
	assert info['currency_symbol'] == '¥'
	assert '¥10.0' in info['display']


def test_get_user_info_defaults_to_dollar(providers):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={'success': True, 'data': {'quota': 500000, 'used_quota': 0}})

	provider = providers['helpcoder']
	with _client(handler, provider) as client:
		info = get_user_info(client, {}, f'{provider.domain}/api/user/self')

	assert info['currency_symbol'] == '$'
	assert '$1.0' in info['display']


def test_get_user_info_reads_nested_user_object(providers):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={'success': True, 'data': {'user': {'quota': 1000000, 'used_quota': 0}}})

	provider = providers['seekai']
	with _client(handler, provider) as client:
		info = get_user_info(client, {}, f'{provider.domain}/api/user/self')

	assert info['quota'] == 2.0


# ------------------------------------------------------- access_token 账号配置


def test_accounts_config_accepts_access_token_only(monkeypatch):
	monkeypatch.setenv(
		'ANYROUTER_ACCOUNTS',
		json.dumps([{'provider': 'hcnsec', 'access_token': 'at-1'}]),
	)

	accounts = load_accounts_config()

	assert accounts is not None
	assert len(accounts) == 1
	assert accounts[0].access_token == 'at-1'
	assert accounts[0].provider == 'hcnsec'
	assert accounts[0].has_login_credentials() is False


def test_accounts_config_rejects_account_without_any_auth(monkeypatch):
	monkeypatch.setenv('ANYROUTER_ACCOUNTS', json.dumps([{'provider': 'hcnsec'}]))

	assert load_accounts_config() is None


def test_accounts_config_accepts_access_token_with_cookies(monkeypatch):
	monkeypatch.setenv(
		'ANYROUTER_ACCOUNTS',
		json.dumps([{'provider': 'seekai', 'access_token': 'at-2', 'cookies': {'session': 's'}}]),
	)

	accounts = load_accounts_config()

	assert accounts is not None
	assert accounts[0].access_token == 'at-2'
	assert accounts[0].cookies == {'session': 's'}


def test_accounts_config_still_accepts_email_password(monkeypatch):
	monkeypatch.setenv(
		'ANYROUTER_ACCOUNTS',
		json.dumps([{'provider': 'seekai', 'email': 'a@b.com', 'password': 'pw'}]),
	)

	accounts = load_accounts_config()

	assert accounts is not None
	assert accounts[0].has_login_credentials() is True
	assert accounts[0].access_token is None
