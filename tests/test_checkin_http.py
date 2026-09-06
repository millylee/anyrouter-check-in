from checkin import get_user_info


class FakeResponse:
	def __init__(self, status_code, payload=None):
		self.status_code = status_code
		self._payload = payload or {}

	def json(self):
		return self._payload


class FakeClient:
	def __init__(self, responses):
		self.responses = iter(responses)
		self.calls = []

	def get(self, url, *, headers, timeout):
		self.calls.append({'url': url, 'headers': headers, 'timeout': timeout})
		return next(self.responses)

	def post(self, url, *, headers, timeout, json=None):
		self.calls.append({'url': url, 'json': json, 'headers': headers, 'timeout': timeout})
		return next(self.responses)


def test_get_user_info_retries_without_stale_api_user_after_401():
	client = FakeClient(
		[
			FakeResponse(401),
			FakeResponse(200, {'success': True, 'data': {'quota': 500000, 'used_quota': 250000}}),
		]
	)

	result = get_user_info(
		client,
		{'new-api-user': 'stale-user', 'Cookie': 'session=valid'},
		'https://anyrouter.top/api/user/self',
		api_user_key='new-api-user',
	)

	assert result == {
		'success': True,
		'quota': 1.0,
		'used_quota': 0.5,
		'display': ':money: Current balance: $1.0, Used: $0.5',
	}
	assert client.calls[0]['headers']['new-api-user'] == 'stale-user'
	assert client.calls[0]['headers']['X-Requested-With'] == 'XMLHttpRequest'
	assert 'new-api-user' not in client.calls[1]['headers']
	assert client.calls[1]['headers']['X-Requested-With'] == 'XMLHttpRequest'


def test_parse_cookies_accepts_full_cookie_request_header():
	from checkin import parse_cookies

	assert parse_cookies('Cookie: session=fresh; cf_clearance=ready') == {
		'session': 'fresh',
		'cf_clearance': 'ready',
	}


class FakeRefreshClient(FakeClient):
	"""GET 走 responses，POST /auth/refresh 单独给一份响应。"""

	def __init__(self, responses, refresh_response):
		super().__init__(responses)
		self.refresh_response = refresh_response
		self.posts = []

	def post(self, url, *, headers, timeout, json=None):
		self.posts.append({'url': url, 'headers': headers, 'timeout': timeout})
		return self.refresh_response


def test_refresh_access_token_returns_rotated_token():
	from checkin import refresh_access_token
	from utils.config import ProviderConfig

	provider = ProviderConfig(name='xiaojimao', domain='https://api.ark717.com')
	client = FakeRefreshClient(
		[],
		FakeResponse(200, {'success': True, 'data': {'access_token': 'rotated', 'token_type': 'Bearer'}}),
	)

	token = refresh_access_token(client, {'Authorization': 'Bearer stale'}, provider, 'acct')

	assert token == 'rotated'
	assert client.posts[0]['url'] == 'https://api.ark717.com/api/user/auth/refresh'
	# 轮换请求不能带过期的 Authorization，否则服务端会直接拒绝。
	assert 'Authorization' not in client.posts[0]['headers']


def test_refresh_access_token_returns_none_on_401():
	from checkin import refresh_access_token
	from utils.config import ProviderConfig

	provider = ProviderConfig(name='xiaojimao', domain='https://api.ark717.com')
	client = FakeRefreshClient([], FakeResponse(401, {'success': False}))

	assert refresh_access_token(client, {}, provider, 'acct') is None


def test_refresh_access_token_skipped_when_provider_has_no_path():
	from checkin import refresh_access_token
	from utils.config import ProviderConfig

	provider = ProviderConfig(name='legacy', domain='https://example.com', auth_refresh_path=None)
	client = FakeRefreshClient([], FakeResponse(200, {'success': True, 'data': {'access_token': 'x'}}))

	assert refresh_access_token(client, {}, provider, 'acct') is None
	assert client.posts == []


def test_execute_captcha_check_in_retries_uncertain_ocr(monkeypatch):
	import json

	from checkin import execute_captcha_check_in
	from utils.config import ProviderConfig

	class Response:
		def __init__(self, status_code, payload):
			self.status_code = status_code
			self._payload = payload
			self.text = json.dumps(payload)

		def json(self):
			return self._payload

	class CaptchaClient:
		def __init__(self):
			self.captcha_count = 0
			self.submissions = []

		def get(self, url, *, headers, timeout):
			self.captcha_count += 1
			return Response(
				200, {'data': {'captcha_id': f'id-{self.captcha_count}', 'image': 'data:image/png;base64,abc'}}
			)

		def post(self, url, *, json, headers, timeout):
			self.submissions.append(json)
			return Response(200, {'success': True})

	client = CaptchaClient()
	provider = ProviderConfig(name='sheapi', domain='https://www.sheapi.top', checkin_captcha=True)
	results = iter(
		[
			type('OCR', (), {'text': '2345', 'exact': False})(),
			type('OCR', (), {'text': '6789', 'exact': True})(),
		]
	)
	monkeypatch.setattr('captcha_ocr.base64_captcha.solve_data_url', lambda image: next(results))

	assert execute_captcha_check_in(client, 'SheApi', provider, {}) is True
	assert client.captcha_count == 2
	assert client.submissions == [{'captcha_id': 'id-2', 'captcha_code': '6789'}]


def test_execute_captcha_check_in_result_keeps_provider_error(monkeypatch):
	import json

	from checkin import execute_captcha_check_in_result
	from utils.config import ProviderConfig

	class Response:
		def __init__(self, status_code, payload):
			self.status_code = status_code
			self._payload = payload
			self.text = json.dumps(payload)

		def json(self):
			return self._payload

	class CaptchaClient:
		def get(self, url, *, headers, timeout):
			return Response(200, {'data': {'captcha_id': 'id-1', 'image': 'data:image/png;base64,abc'}})

		def post(self, url, *, json, headers, timeout):
			return Response(200, {'success': False, 'message': '该 IP 签到账号数量过多，请稍后再试'})

	provider = ProviderConfig(name='sheapi', domain='https://www.sheapi.top', checkin_captcha=True)
	monkeypatch.setattr(
		'captcha_ocr.base64_captcha.solve_data_url',
		lambda image: type('OCR', (), {'text': '6789', 'exact': True})(),
	)

	assert execute_captcha_check_in_result(CaptchaClient(), 'SheApi', provider, {}) == (
		False,
		'Check-in failed - 该 IP 签到账号数量过多，请稍后再试',
	)


def test_get_user_info_includes_gift_quota_in_balance():
	client = FakeClient([FakeResponse(200, {'success': True, 'data': {'quota': 70464, 'gift_quota': 121430385}})])

	result = get_user_info(client, {'Cookie': 'session=valid'}, 'https://api.gemai.cc/api/user/self')

	assert result['quota'] == 243.0
	assert result['display'] == ':money: Current balance: $243.0, Used: $0.0'
