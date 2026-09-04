"""从登录到签到的完整链路测试（不启动浏览器，全部走 mock transport）"""

import json

import httpx
import pytest

import checkin as checkin_module
import utils.api_login as api_login
from checkin import check_in_account
from utils.config import AccountConfig, AppConfig


@pytest.fixture
def app_config(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	return AppConfig.load_from_env()


class _NoClose:
	def __init__(self, inner):
		self._inner = inner

	def __enter__(self):
		return self._inner

	def __exit__(self, *exc):
		return False


@pytest.fixture
def fake_transport(monkeypatch):
	"""让 api_login 与 checkin 共用同一个 mock transport。"""

	# api_login.httpx 与 checkin.httpx 是同一个模块对象，先存下原始类避免工厂自我递归
	real_client = httpx.Client

	def install(handler):
		def factory(**kwargs):
			return _NoClose(real_client(transport=httpx.MockTransport(handler)))

		monkeypatch.setattr(api_login.httpx, 'Client', factory)
		monkeypatch.setattr(checkin_module.httpx, 'Client', factory)

	return install


def _newapi_server(*, bearer_required: bool, turnstile_required: bool, already_checked_in: bool = False):
	"""模拟一个 NewAPI 站点，记录收到的请求以便断言。"""
	log: dict = {'checkin_posts': [], 'auth_headers': [], 'checked_in': already_checked_in}

	def handler(request: httpx.Request) -> httpx.Response:
		path = request.url.path
		auth = request.headers.get('authorization')

		if path == '/api/user/login':
			body = json.loads(request.content)
			log['login_body'] = body
			return httpx.Response(
				200,
				json={
					'success': True,
					'data': {
						'access_token': 'at-e2e',
						'token_type': 'Bearer',
						'user': {'id': 4590, 'username': 'demo'},
					},
				},
				headers={'set-cookie': 'new_api_has_session=1; Path=/'},
			)

		# 新版仪表盘只认 Bearer，没带就返回未授权
		if bearer_required and auth != 'Bearer at-e2e':
			return httpx.Response(200, json={'success': False, 'message': 'unauthorized'})

		if path == '/api/user/self':
			log['auth_headers'].append(auth)
			quota = 5000000 if log['checked_in'] else 2500000
			return httpx.Response(200, json={'success': True, 'data': {'quota': quota, 'used_quota': 500000}})

		if path == '/api/user/checkin':
			if request.method == 'GET':
				return httpx.Response(
					200,
					json={'success': True, 'data': {'enabled': True, 'stats': {'checked_in_today': log['checked_in']}}},
				)
			log['checkin_posts'].append(str(request.url))
			if turnstile_required and not request.url.params.get('turnstile'):
				return httpx.Response(200, json={'success': False, 'message': 'Turnstile token 为空'})
			log['checked_in'] = True
			return httpx.Response(
				200,
				json={'success': True, 'message': '签到成功', 'data': {'quota_awarded': 2500000}},
			)

		return httpx.Response(404, json={'success': False, 'message': 'not found'})

	return handler, log


async def test_api_login_site_completes_check_in(app_config, fake_transport):
	"""hcnsec：JSON 登录 -> Bearer 鉴权 -> 查状态 -> 签到"""
	handler, log = _newapi_server(bearer_required=True, turnstile_required=False)
	fake_transport(handler)

	account = AccountConfig(cookies=None, provider='hcnsec', email='a@b.com', password='pw')
	success, before, after = await check_in_account(account, 0, app_config)

	assert success is True
	assert log['login_body'] == {'username': 'a@b.com', 'password': 'pw'}
	assert log['auth_headers'] == ['Bearer at-e2e', 'Bearer at-e2e']
	assert len(log['checkin_posts']) == 1
	# 额度按 500000 = 1 单位换算，并使用 hcnsec 的 ¥ 符号
	assert before['quota'] == 5.0
	assert after['quota'] == 10.0
	assert after['currency_symbol'] == '¥'


async def test_api_login_site_skips_post_when_already_checked_in(app_config, fake_transport):
	handler, log = _newapi_server(bearer_required=True, turnstile_required=False, already_checked_in=True)
	fake_transport(handler)

	account = AccountConfig(cookies=None, provider='hcnsec', email='a@b.com', password='pw')
	success, _, _ = await check_in_account(account, 0, app_config)

	assert success is True
	assert log['checkin_posts'] == []


async def test_cookie_site_completes_check_in_without_bearer(app_config, fake_transport):
	"""helpcoder：旧版 cookie 鉴权，签到不带 turnstile"""
	handler, log = _newapi_server(bearer_required=False, turnstile_required=False)
	fake_transport(handler)

	account = AccountConfig(cookies=None, provider='helpcoder', email='a@b.com', password='pw')
	success, _, after = await check_in_account(account, 0, app_config)

	assert success is True
	assert len(log['checkin_posts']) == 1
	assert 'turnstile' not in log['checkin_posts'][0]
	assert after['currency_symbol'] == '$'


async def test_access_token_account_skips_login(app_config, fake_transport):
	"""只配 access_token 时不应调用登录接口"""
	handler, log = _newapi_server(bearer_required=True, turnstile_required=False)
	fake_transport(handler)

	account = AccountConfig(cookies=None, provider='hcnsec', access_token='at-e2e')
	success, _, _ = await check_in_account(account, 0, app_config)

	assert success is True
	assert 'login_body' not in log
	assert len(log['checkin_posts']) == 1


async def test_bearer_site_fails_cleanly_without_token(app_config, fake_transport):
	"""没有 access_token 时新版仪表盘应判定失败，而不是误报成功"""
	handler, log = _newapi_server(bearer_required=True, turnstile_required=False)
	fake_transport(handler)

	account = AccountConfig(cookies={'session': 'stale'}, api_user='4590', provider='hcnsec')
	success, _, _ = await check_in_account(account, 0, app_config)

	assert success is False
	assert log['checkin_posts'] == []


async def test_turnstile_site_retries_then_succeeds(app_config, fake_transport):
	"""seekai：POST 缺 token 被拒后，带上浏览器领到的 token 重试"""
	handler, log = _newapi_server(bearer_required=True, turnstile_required=True)
	fake_transport(handler)

	success, _, _ = checkin_module.run_check_in_requests(
		{'new_api_has_session': '1'},
		AccountConfig(cookies=None, provider='seekai'),
		'SeekAI',
		app_config.get_provider('seekai'),
		api_user_override='4590',
		access_token='at-e2e',
		turnstile_token='ts-token',
	)

	assert success is True
	assert len(log['checkin_posts']) == 1
	assert 'turnstile=ts-token' in log['checkin_posts'][0]


async def test_tabitoken_check_in_carries_turnstile_and_bearer(app_config, fake_transport):
	"""tabitoken：浏览器登录后带 Bearer 与 Turnstile token 完成签到"""
	handler, log = _newapi_server(bearer_required=True, turnstile_required=True)
	fake_transport(handler)

	provider = app_config.get_provider('tabitoken')
	success, _, after = checkin_module.run_check_in_requests(
		{'cf_clearance': 'cf-1'},
		AccountConfig(cookies=None, provider='tabitoken'),
		'TaBiAI',
		provider,
		api_user_override='4590',
		access_token='at-e2e',
		turnstile_token='ts-tabi',
	)

	assert success is True
	assert log['auth_headers'] == ['Bearer at-e2e', 'Bearer at-e2e']
	assert len(log['checkin_posts']) == 1
	assert 'turnstile=ts-tabi' in log['checkin_posts'][0]
	assert after['currency_symbol'] == '$'


async def test_failed_login_does_not_fall_back_to_stale_cookies(app_config, fake_transport):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == '/api/user/login':
			return httpx.Response(200, json={'success': False, 'message': '用户名或密码错误，或用户已被封禁'})
		raise AssertionError('must not issue requests after a failed login')

	fake_transport(handler)

	account = AccountConfig(
		cookies={'session': 'stale'},
		api_user='4590',
		provider='helpcoder',
		email='a@b.com',
		password='wrong',
	)
	success, before, after = await check_in_account(account, 0, app_config)

	assert success is False
	assert before is None
	assert after is None
