import json

from utils.config import AppConfig, ProviderConfig


def test_builtin_provider_profile_persistence_defaults(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)

	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].persist_profile is True
	assert config.providers['agentrouter'].persist_profile is False


def test_futureppo_provider_is_builtin():
	config = AppConfig.load_from_env()

	provider = config.providers['futureppo']

	assert provider.domain == 'https://api.futureppo.top'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.waf_cookie_names == ['cf_clearance']
	assert provider.use_proxy is True


def test_provider_profile_persistence_can_override_builtin(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps(
			{
				'anyrouter': {'domain': 'https://anyrouter.top', 'persist_profile': False},
				'agentrouter': {'domain': 'https://agentrouter.org', 'persist_profile': True},
			}
		),
	)

	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].persist_profile is False
	assert config.providers['agentrouter'].persist_profile is True


def test_custom_provider_profile_persistence_defaults_to_false(monkeypatch):
	monkeypatch.setenv('PROVIDERS', json.dumps({'custom': {'domain': 'https://custom.example.com'}}))

	config = AppConfig.load_from_env()

	assert config.providers['custom'].persist_profile is False


def test_provider_from_dict_inherits_profile_persistence_from_defaults():
	defaults = ProviderConfig(name='custom', domain='https://old.example.com', persist_profile=True)

	provider = ProviderConfig.from_dict(
		'custom',
		{'domain': 'https://new.example.com'},
		defaults=defaults,
	)

	assert provider.persist_profile is True


def test_extra_providers_are_merged_after_main_providers(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps({'custom': {'domain': 'https://old.example.com', 'use_proxy': True}}),
	)
	monkeypatch.setenv(
		'EXTRA_PROVIDERS',
		json.dumps(
			{
				'custom': {'domain': 'https://new.example.com'},
				'futureppo': {
					'domain': 'https://api.futureppo.top',
					'sign_in_path': '/api/user/checkin',
				},
			}
		),
	)

	config = AppConfig.load_from_env()

	assert config.providers['custom'].domain == 'https://new.example.com'
	assert config.providers['custom'].use_proxy is True
	assert config.providers['futureppo'].sign_in_path == '/api/user/checkin'


def test_twinkle_sub2api_provider_is_built_in(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['twinkle']

	assert provider.api_style == 'sub2api'
	assert provider.domain == 'https://big-model.smart-agi.com'
	assert provider.login_api_path == '/api/v1/auth/login'
	assert provider.sign_in_path == '/api/v1/user/daily-checkin'
	assert provider.user_info_path == '/api/v1/user/profile'
	assert provider.use_proxy is True


def test_42w_provider_uses_browser_page_for_cloudflare(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['42w']

	assert provider.domain == 'https://api.42w.shop'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.waf_cookie_names == ['cf_clearance']
	assert provider.use_proxy is True
	assert provider.http2 is False
	assert provider.request_in_page is True


def test_kapibala_provider_uses_newapi_refresh_auth(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['kapibala']

	assert provider.domain == 'https://kapibala.asia'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.use_proxy is False


def test_nianhua_provider_uses_password_login(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['nianhua']

	assert provider.domain == 'https://us-3.nianhuaapi.com'
	assert provider.login_api_path == '/api/user/login'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.use_proxy is False


def test_sheapi_provider_uses_local_captcha_ocr(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['sheapi']

	assert provider.domain == 'https://www.sheapi.top'
	assert provider.login_api_path == '/api/user/login'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.checkin_captcha is True
	assert provider.captcha_path == '/api/captcha?scene=checkin'
	assert provider.use_proxy is True


def test_aiaiai_provider_uses_cookie_auth(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['aiaiai']

	assert provider.domain == 'https://api.aiaiai001.com'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.login_api_path is None
	assert provider.use_proxy is False


def test_guyscode_provider_uses_tokenrouter_check_in_api(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['guyscode']

	assert provider.api_style == 'tokenrouter'
	assert provider.domain == 'https://www.guyscode.com'
	assert provider.login_api_path == '/api/v1/auth/login'
	assert provider.sign_in_path == '/api/v1/check-in'
	assert provider.check_in_status_path == '/api/v1/check-in/status'
	assert provider.user_info_path == '/api/v1/auth/me'
	assert provider.auth_refresh_path == '/api/v1/auth/refresh'
	assert provider.api_user_key == ''
	assert provider.use_proxy is False


def test_xiaobai_provider_uses_external_check_in_api(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['xiaobai']

	assert provider.api_style == 'xiaobai'
	assert provider.domain == 'https://token.dialoguedui.com'
	assert provider.sign_in_path == '/checkin/api/checkin'
	assert provider.check_in_status_path == '/checkin/api/status'
	assert provider.auth_refresh_path == '/api/v1/auth/refresh'
	assert provider.api_user_key == ''
	assert provider.use_proxy is False


def test_gorouter_provider_uses_pat_and_turnstile(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	provider = config.providers['gorouter']

	assert provider.domain == 'https://gorouter.app'
	# /profile 会被 openresty 302 到 /dashboard/overview，签到卡片只在 /console/personal 挂载。
	assert provider.login_path == '/console/personal'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.checkin_turnstile is True
	assert provider.turnstile_site_key == '0x4AAAAAAELziOpg1Y2gFtAt'
	assert provider.persist_profile is True


def test_gorouter_provider_flags_can_be_overridden(monkeypatch):
	monkeypatch.setenv(
		'EXTRA_PROVIDERS',
		json.dumps(
			{
				'gorouter': {
					'domain': 'https://example.com',
					'checkin_turnstile': False,
					'persist_profile': False,
					'turnstile_site_key': '0xOVERRIDE',
				}
			}
		),
	)

	provider = AppConfig.load_from_env().providers['gorouter']

	assert provider.domain == 'https://example.com'
	assert provider.checkin_turnstile is False
	assert provider.persist_profile is False
	assert provider.turnstile_site_key == '0xOVERRIDE'


def test_qingjiu_provider_uses_browser_page_for_login_session(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['qingjiu']

	assert provider.domain == 'https://qingjiu.nemodesk.top'
	assert provider.login_path == '/login'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.http2 is False
	assert provider.request_in_page is True


def test_qingjiu_custom_provider_inherits_browser_request_defaults(monkeypatch):
	monkeypatch.setenv('PROVIDERS', json.dumps({'qingjiu': {'domain': 'https://qingjiu.nemodesk.top'}}))
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['qingjiu']

	assert provider.http2 is False
	assert provider.request_in_page is True


def test_justwoker_provider_uses_pat_and_turnstile(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['justwoker']

	# 与 gorouter 同构的 NewAPI：签到必须带 Turnstile token，且只接受 ?turnstile= 查询参数。
	assert provider.domain == 'https://api.justwoker.icu'
	assert provider.login_path == '/console/personal'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.use_proxy is False
	assert provider.checkin_turnstile is True
	assert provider.turnstile_site_key == '0x4AAAAAAEQ0v37GMr9cC_Kw'
	assert provider.persist_profile is True


def test_tabitoken_provider_uses_pat_and_turnstile(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['tabitoken']

	# 与 gorouter/justwoker 同构的 NewAPI；/profile 会 302，签到卡片只在 /console/personal 挂载。
	assert provider.domain == 'https://tabitoken.com'
	assert provider.login_path == '/console/personal'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.use_proxy is False
	assert provider.checkin_turnstile is True
	assert provider.turnstile_site_key == '0x4AAAAAAEGV81TArluaPQGB'
	assert provider.persist_profile is True


def test_simple_newapi_pat_providers_are_builtin(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	providers = AppConfig.load_from_env().providers
	expected_domains = {
		'ciyuan': 'https://ai.962831.xyz',
		'yuecheng': 'https://52ccl.net',
		'elysiver': 'https://elysiver.h-e.top',
		'windhub': 'https://windhub.cc',
	}

	for name, domain in expected_domains.items():
		provider = providers[name]
		assert provider.domain == domain
		assert provider.sign_in_path == '/api/user/checkin'
		assert provider.user_info_path == '/api/user/self'
		assert provider.auth_refresh_path == '/api/user/auth/refresh'
		assert provider.api_user_key == 'New-Api-User'
		assert provider.use_proxy is False


def test_ciyuan_provider_uses_turnstile(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['ciyuan']

	# The public /api/status response has turnstile_check enabled. A plain
	# POST returns HTTP 200 with "Turnstile token 为空", so use the same
	# browser-minted token flow as the other current NewAPI deployments.
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.checkin_turnstile is True
	assert provider.turnstile_site_key == '0x4AAAAAADub4IXwHwHzJPGa'
	assert provider.persist_profile is True


def test_windhub_provider_is_builtin(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['windhub']

	# Ark API（https://windhub.cc）是挂在 Cloudflare 后面的新版 NewAPI，但站点
	# 关掉了 turnstile_check，且 CF 不对 /api 下的接口发起挑战，所以既不需要
	# Turnstile，也不需要 WAF cookie/页内请求，直接用 httpx + 系统访问令牌即可。
	assert provider.domain == 'https://windhub.cc'
	assert provider.login_path == '/console/personal'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.use_proxy is False
	assert provider.checkin_turnstile is False
	assert provider.bypass_method is None
	assert provider.request_in_page is False
	assert provider.http2 is True


def test_laomo_provider_is_builtin(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['laomo']

	# 老魔公益站（https://api.2020111.xyz）与 gorouter/justwoker/tabitoken 同构：
	# 站点 turnstile_check 为开启，POST /api/user/checkin 缺 token 时返回
	# 「Turnstile token 为空」，因此复用页内渲染 widget 取 token 的流程。
	assert provider.domain == 'https://api.2020111.xyz'
	assert provider.login_path == '/console/personal'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.use_proxy is False
	assert provider.checkin_turnstile is True
	assert provider.turnstile_site_key == '0x4AAAAAAD5FNNbWZboF0Wzx'
	assert provider.persist_profile is True


def test_nhh123_provider_is_builtin(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['nhh123']

	# 123NHH 是新版 NewAPI，但站点关闭了 Turnstile；Bearer PAT 与
	# New-Api-User 头可直接访问用户信息和签到接口。
	assert provider.domain == 'https://api.123nhh.com'
	assert provider.login_path == '/profile'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.use_proxy is False
	assert provider.checkin_turnstile is False
	assert provider.bypass_method is None
	assert provider.request_in_page is False
	assert provider.http2 is True


def test_superapi_provider_is_builtin(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['superapi']

	# SuperAPI 是新版 NewAPI，站点关闭了 Turnstile；Bearer PAT 与
	# New-Api-User 头可直接访问用户信息和签到接口。
	assert provider.domain == 'https://superapi.buzz'
	assert provider.login_path == '/profile'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.use_proxy is False
	assert provider.checkin_turnstile is False
	assert provider.bypass_method is None
	assert provider.request_in_page is False
	assert provider.http2 is True


def test_gemai_provider_uses_newapi_pat_without_turnstile(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)

	provider = AppConfig.load_from_env().providers['gemai']

	assert provider.domain == 'https://api.gemai.cc'
	assert provider.api_style == 'newapi'
	assert provider.login_path == '/profile'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.check_in_status_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.auth_refresh_path == '/api/user/auth/refresh'
	assert provider.api_user_key == 'New-Api-User'
	assert provider.use_proxy is False
	assert provider.checkin_turnstile is False
	assert provider.checkin_captcha is False
	assert provider.bypass_method is None
	assert provider.request_in_page is False
	assert provider.http2 is True
