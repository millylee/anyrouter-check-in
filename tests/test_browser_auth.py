"""浏览器登录判定与新版 NewAPI 会话解析测试"""

import pytest

from utils.browser import (
	AuthCapture,
	_extract_user_profile,
	has_session_cookie,
	is_logged_in,
	read_stored_access_token,
)


class FakeContext:
	def __init__(self, cookies=None):
		self._cookies = cookies or []

	async def cookies(self):
		return self._cookies


class FakeLocator:
	def __init__(self, visible=False, raises=False):
		self._visible = visible
		self._raises = raises

	@property
	def first(self):
		return self

	async def is_visible(self):
		if self._raises:
			raise RuntimeError('detached')
		return self._visible


class FakePage:
	def __init__(self, url='https://x.example.com/', cookies=None, locator_visible=False, eval_result=None):
		self.url = url
		self.context = FakeContext(cookies)
		self._locator_visible = locator_visible
		self._eval_result = eval_result
		self.handlers: list = []

	def locator(self, selector):
		return FakeLocator(visible=self._locator_visible)

	async def evaluate(self, script, *args):
		if isinstance(self._eval_result, Exception):
			raise self._eval_result
		return self._eval_result

	def on(self, event, handler):
		self.handlers.append((event, handler))

	def remove_listener(self, event, handler):
		self.handlers.remove((event, handler))


class FakeResponse:
	def __init__(self, url, status=200, payload=None, raises=False):
		self.url = url
		self.status = status
		self._payload = payload
		self._raises = raises

	async def json(self):
		if self._raises:
			raise ValueError('not json')
		return self._payload


# ----------------------------------------------------------------- 登录状态判定


@pytest.mark.parametrize(
	'url',
	[
		'https://helpcoder.cc/console',
		'https://helpcoder.cc/console/personal',
		'https://seekai.cc/dashboard',
		'https://api.hcnsec.cn/dashboard/token',
		'https://gorouter.app/profile',
		'https://api.justwoker.icu/profile/',
	],
)
async def test_is_logged_in_accepts_dashboard_urls(url):
	assert await is_logged_in(FakePage(url=url)) is True


@pytest.mark.parametrize(
	'url',
	[
		'https://seekai.cc/sign-in',
		'https://helpcoder.cc/login',
		'https://gorouter.app/signin',
		'https://seekai.cc/sign-in?redirect=/dashboard',
	],
)
async def test_is_logged_in_rejects_login_urls(url):
	assert await is_logged_in(FakePage(url=url)) is False


async def test_is_logged_in_rejects_landing_page_with_email_entry():
	page = FakePage(url='https://anyrouter.top/', locator_visible=True)

	assert await is_logged_in(page) is False


# --------------------------------------------------------------------- cookies


async def test_has_session_cookie_detects_classic_session():
	page = FakePage(cookies=[{'name': 'session', 'value': 'abc'}])

	assert await has_session_cookie(page) is True


async def test_has_session_cookie_detects_new_api_hint_cookie():
	page = FakePage(cookies=[{'name': 'new_api_has_session', 'value': '1'}])

	assert await has_session_cookie(page) is True


async def test_has_session_cookie_ignores_unrelated_or_empty_cookies():
	page = FakePage(cookies=[{'name': 'acw_tc', 'value': 'x'}, {'name': 'session', 'value': ''}])

	assert await has_session_cookie(page) is False


# ---------------------------------------------------------------- 用户档案解析


@pytest.mark.parametrize(
	('payload', 'expected_id'),
	[
		({'success': True, 'data': {'id': 123, 'username': 'a'}}, 123),
		({'success': True, 'data': {'user': {'id': 456}, 'access_token': 't'}}, 456),
		({'id': 789}, 789),
	],
)
def test_extract_user_profile_supports_both_shapes(payload, expected_id):
	profile = _extract_user_profile(payload)

	assert profile is not None
	assert profile['id'] == expected_id


@pytest.mark.parametrize(
	'payload',
	[
		{'success': False, 'message': 'unauthorized'},
		{'success': True, 'data': {}},
		{'success': True, 'data': None},
		{'data': {'user': {'username': 'no-id'}}},
		'not-a-dict',
		None,
	],
)
def test_extract_user_profile_rejects_unusable_payloads(payload):
	assert _extract_user_profile(payload) is None


# ------------------------------------------------------- localStorage 会话读取


async def test_read_stored_access_token_from_auth_session():
	page = FakePage(eval_result={'access_token': 'at-1', 'user': {'id': 5}})

	assert await read_stored_access_token(page) == 'at-1'


async def test_read_stored_access_token_returns_none_without_session():
	assert await read_stored_access_token(FakePage(eval_result=None)) is None


async def test_read_stored_access_token_survives_evaluate_failure():
	assert await read_stored_access_token(FakePage(eval_result=RuntimeError('no page'))) is None


# ------------------------------------------------------------------ AuthCapture


async def test_auth_capture_collects_token_and_profile_from_login():
	page = FakePage()
	capture = AuthCapture(page)
	capture.start()

	await capture._on_response(
		FakeResponse(
			'https://seekai.cc/api/user/login?turnstile=x',
			payload={'success': True, 'data': {'access_token': 'at-9', 'user': {'id': 4590}}},
		)
	)

	assert capture.access_token == 'at-9'
	assert capture.user_profile is not None
	assert capture.user_profile['id'] == 4590


async def test_auth_capture_collects_profile_from_user_self():
	capture = AuthCapture(FakePage())

	await capture._on_response(
		FakeResponse('https://seekai.cc/api/user/self', payload={'success': True, 'data': {'id': 7}})
	)

	assert capture.user_profile is not None
	assert capture.user_profile['id'] == 7
	assert capture.access_token is None


@pytest.mark.parametrize(
	'response',
	[
		FakeResponse('https://seekai.cc/api/status', payload={'success': True, 'data': {'id': 1}}),
		FakeResponse('https://seekai.cc/api/user/login', status=401, payload={'success': False}),
		FakeResponse('https://seekai.cc/api/user/self', raises=True),
		FakeResponse('https://seekai.cc/api/user/self', payload=['not', 'a', 'dict']),
	],
)
async def test_auth_capture_ignores_irrelevant_or_broken_responses(response):
	capture = AuthCapture(FakePage())

	await capture._on_response(response)

	assert capture.access_token is None
	assert capture.user_profile is None


async def test_auth_capture_start_and_stop_are_idempotent():
	page = FakePage()
	capture = AuthCapture(page)

	capture.start()
	capture.start()
	assert len(page.handlers) == 1

	capture.stop()
	capture.stop()
	assert page.handlers == []


async def test_auth_capture_snapshot_falls_back_to_page_state():
	page = FakePage(eval_result={'access_token': 'at-stored', 'user': {'id': 11}})
	capture = AuthCapture(page)

	await capture.snapshot_from_page()

	assert capture.access_token == 'at-stored'
	assert capture.user_profile is not None
	assert capture.user_profile['id'] == 11
