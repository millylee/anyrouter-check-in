"""sotamodel provider 的配置、JSON 登录与签到判定测试"""

import json

import httpx
import pytest

from checkin import execute_check_in, fetch_check_in_status, is_already_checked_in
from utils.api_login import login_via_api
from utils.config import AppConfig, ProviderConfig


@pytest.fixture
def sotamodel(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	provider = AppConfig.load_from_env().get_provider('sotamodel')
	assert provider is not None
	return provider


def _client(handler, provider) -> httpx.Client:
	return httpx.Client(transport=httpx.MockTransport(handler), base_url=provider.domain)


# ---------------------------------------------------------------- provider 配置


def test_sotamodel_is_builtin(sotamodel):
	assert sotamodel.domain == 'https://sotamodel.net'
	assert sotamodel.login_path == '/sign-in'
	assert sotamodel.login_api_path == '/api/user/login'
	assert sotamodel.sign_in_path == '/api/user/sota-agent-checkin'
	assert sotamodel.check_in_status_path == '/api/user/sota-agent-checkin'
	assert sotamodel.user_info_path == '/api/user/self'
	assert sotamodel.api_user_key == 'new-api-user'


def test_sotamodel_needs_no_browser_or_waf(sotamodel):
	assert sotamodel.uses_api_login() is True
	assert sotamodel.needs_waf_cookies() is False
	assert sotamodel.needs_manual_check_in() is True
	assert sotamodel.persist_profile is False
	# 内置 provider 统一默认走代理，未设置 CHECKIN_PROXY_URL 时只告警不失败
	assert sotamodel.use_proxy is True


def test_sotamodel_fields_can_be_overridden(monkeypatch):
	monkeypatch.setenv('PROVIDERS', json.dumps({'sotamodel': {'domain': 'https://mirror.example.com'}}))

	provider = AppConfig.load_from_env().get_provider('sotamodel')

	# 覆盖 domain 时其余内置字段应从默认值继承
	assert provider.domain == 'https://mirror.example.com'
	assert provider.login_method == 'api'
	assert provider.sign_in_path == '/api/user/sota-agent-checkin'
	assert provider.check_in_status_path == '/api/user/sota-agent-checkin'


def test_other_providers_still_use_browser_login(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].uses_api_login() is False
	assert config.providers['agentrouter'].uses_api_login() is False
	assert config.providers['anyrouter'].check_in_status_path is None


def test_custom_provider_defaults_to_browser_login(monkeypatch):
	monkeypatch.setenv('PROVIDERS', json.dumps({'custom': {'domain': 'https://custom.example.com'}}))

	provider = AppConfig.load_from_env().get_provider('custom')

	assert provider.uses_api_login() is False
	assert provider.login_api_path == '/api/user/login'


def test_provider_can_opt_into_api_login(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps({'custom': {'domain': 'https://custom.example.com', 'login_method': 'api'}}),
	)

	assert AppConfig.load_from_env().get_provider('custom').uses_api_login() is True


# ------------------------------------------------------------------ JSON 登录


def test_login_via_api_returns_cookies_and_api_user(sotamodel):
	seen = {}

	def handler(request: httpx.Request) -> httpx.Response:
		seen['url'] = str(request.url)
		seen['body'] = json.loads(request.content)
		return httpx.Response(
			200,
			json={'success': True, 'message': '', 'data': {'id': 54321, 'username': 'demo'}},
			headers={'set-cookie': 'session=sess-abc; Path=/'},
		)

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		result = _login_with_client(client, sotamodel)

	assert result is not None
	assert result.api_user == '54321'
	assert result.cookies['session'] == 'sess-abc'
	assert seen['body'] == {'username': 'a@b.com', 'password': 'pw'}
	# 站点未开启 turnstile，但接口要求该查询参数存在
	assert 'turnstile=' in seen['url']
	assert seen['url'].startswith('https://sotamodel.net/api/user/login')


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


def test_login_via_api_rejects_bad_credentials(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		# 服务端凭据错误时仍返回 HTTP 200，必须依据 success 字段判断
		return httpx.Response(200, json={'success': False, 'message': '用户名或密码错误，或用户已被封禁'})

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		assert _login_with_client(client, sotamodel) is None


def test_login_via_api_rejects_2fa_accounts(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={'success': True, 'data': {'require_2fa': True}})

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		assert _login_with_client(client, sotamodel) is None


def test_login_via_api_rejects_success_without_cookies(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={'success': True, 'data': {'id': 1}})

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		assert _login_with_client(client, sotamodel) is None


def test_login_via_api_falls_back_to_user_self_for_api_user(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == '/api/user/login':
			return httpx.Response(
				200,
				json={'success': True, 'data': {}},
				headers={'set-cookie': 'session=sess-xyz; Path=/'},
			)
		return httpx.Response(200, json={'success': True, 'data': {'id': 777}})

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		result = _login_with_client(client, sotamodel)

	assert result is not None
	assert result.api_user == '777'


def test_login_via_api_handles_non_json_response(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, text='<html>gateway</html>')

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		assert _login_with_client(client, sotamodel) is None


def test_login_via_api_handles_http_error(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(502, text='bad gateway')

	with httpx.Client(transport=httpx.MockTransport(handler)) as client:
		assert _login_with_client(client, sotamodel) is None


def test_login_via_api_handles_network_error(sotamodel, monkeypatch):
	def boom(**kwargs):
		raise httpx.ConnectError('no route to host')

	monkeypatch.setattr(httpx, 'Client', boom)
	assert login_via_api('Test', sotamodel, 'a@b.com', 'pw') is None


# --------------------------------------------------------------- 签到状态判定


def test_fetch_check_in_status_reads_checked_in_today(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		assert request.method == 'GET'
		return httpx.Response(200, json={'success': True, 'data': {'checked_in_today': True, 'reward_credits': 5}})

	with _client(handler, sotamodel) as client:
		status = fetch_check_in_status(client, 'Test', sotamodel, {})

	assert status == {'checked_in_today': True, 'reward_credits': 5}


def test_fetch_check_in_status_returns_none_without_status_path():
	provider = ProviderConfig(name='x', domain='https://x.example.com')

	def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - 不应被调用
		raise AssertionError('should not issue a request')

	with _client(handler, provider) as client:
		assert fetch_check_in_status(client, 'Test', provider, {}) is None


def test_fetch_check_in_status_tolerates_unauthorized(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(401, json={'success': False, 'message': 'Unauthorized'})

	with _client(handler, sotamodel) as client:
		assert fetch_check_in_status(client, 'Test', sotamodel, {}) is None


def test_execute_check_in_skips_post_when_already_checked_in(sotamodel):
	calls = []

	def handler(request: httpx.Request) -> httpx.Response:
		calls.append(request.method)
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'checked_in_today': True, 'reward_credits': 5}})
		raise AssertionError('check-in POST must be skipped')

	with _client(handler, sotamodel) as client:
		assert execute_check_in(client, 'Test', sotamodel, {}) is True

	assert calls == ['GET']


def test_execute_check_in_posts_when_not_yet_checked_in(sotamodel):
	calls = []

	def handler(request: httpx.Request) -> httpx.Response:
		calls.append(request.method)
		if request.method == 'GET':
			return httpx.Response(200, json={'success': True, 'data': {'checked_in_today': False, 'reward_credits': 5}})
		return httpx.Response(
			200,
			json={'success': True, 'data': {'reward_credits': 5, 'quota_awarded': 2500000, 'current_quota': 5000000}},
		)

	with _client(handler, sotamodel) as client:
		assert execute_check_in(client, 'Test', sotamodel, {}) is True

	assert calls == ['GET', 'POST']


def test_execute_check_in_treats_once_per_day_message_as_success(sotamodel):
	"""状态接口不可用时，退回到多语言提示匹配"""

	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(500, text='oops')
		return httpx.Response(200, json={'success': False, 'message': 'You can only check in once per day'})

	with _client(handler, sotamodel) as client:
		assert execute_check_in(client, 'Test', sotamodel, {}) is True


def test_execute_check_in_reports_real_failure(sotamodel):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == 'GET':
			return httpx.Response(500, text='oops')
		return httpx.Response(200, json={'success': False, 'message': 'Check-in is not enabled'})

	with _client(handler, sotamodel) as client:
		assert execute_check_in(client, 'Test', sotamodel, {}) is False


@pytest.mark.parametrize(
	'message',
	[
		'You can only check in once per day',
		'Do not repeat check-in; only once per day',
		'每日仅可签到一次，请勿重复签到',
		'今日已签到',
		'已经签到过了',
		'Already checked in today',
		'ALREADY SIGNED IN',
	],
)
def test_is_already_checked_in_true(message):
	assert is_already_checked_in(message) is True


@pytest.mark.parametrize(
	'message',
	['', 'Check-in failed', 'Check-in is not enabled', 'Unauthorized, not logged in', 'internal server error'],
)
def test_is_already_checked_in_false(message):
	assert is_already_checked_in(message) is False
