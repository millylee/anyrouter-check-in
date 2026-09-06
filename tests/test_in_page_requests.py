import json

from checkin import parse_check_in_response, parse_user_info_response
from utils.config import AppConfig, ProviderConfig


def test_futureppo_uses_in_page_requests(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)
	config = AppConfig.load_from_env()

	# 机房 IP 上 CF 会查 TLS 指纹，httpx 过不去，必须由页面自己发请求。
	assert config.providers['futureppo'].request_in_page is True


def test_other_providers_keep_httpx_path(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)
	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].request_in_page is False
	assert config.providers['agentrouter'].request_in_page is False


def test_request_in_page_inherits_builtin_default(monkeypatch):
	monkeypatch.setenv('EXTRA_PROVIDERS', '{"futureppo": {"domain": "https://api.futureppo.top"}}')
	monkeypatch.delenv('PROVIDERS', raising=False)
	config = AppConfig.load_from_env()

	assert config.providers['futureppo'].request_in_page is True


def test_qingjiu_uses_in_page_requests(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	monkeypatch.delenv('EXTRA_PROVIDERS', raising=False)
	config = AppConfig.load_from_env()

	assert config.providers['qingjiu'].request_in_page is True


def test_request_in_page_opt_in_from_dict():
	provider = ProviderConfig.from_dict('c', {'domain': 'https://e.com', 'request_in_page': True})
	assert provider.request_in_page is True


def test_parse_check_in_success():
	assert parse_check_in_response('x', 200, json.dumps({'success': True})) is True


def test_parse_check_in_already_checked_in():
	# 站点把"今日已签到"返回成 success=false，不能算失败。
	assert parse_check_in_response('x', 200, json.dumps({'message': '今日已签到', 'success': False})) is True


def test_parse_check_in_real_failure():
	assert parse_check_in_response('x', 200, json.dumps({'message': '额度不足', 'success': False})) is False


def test_parse_check_in_non_200():
	assert parse_check_in_response('x', 403, 'blocked') is False


def test_parse_check_in_already_claimed_conflict():
	body = json.dumps({'code': 409, 'message': 'check-in already claimed today'})
	assert parse_check_in_response('x', 409, body) is True


def test_parse_check_in_non_json_success():
	assert parse_check_in_response('x', 200, 'SUCCESS') is True


def test_parse_user_info_extracts_balance():
	body = json.dumps({'success': True, 'data': {'quota': 500000, 'used_quota': 250000}})
	info = parse_user_info_response(200, body)
	assert info['success'] is True
	assert info['quota'] == 1.0
	assert info['used_quota'] == 0.5


def test_parse_user_info_non_200():
	assert parse_user_info_response(403, 'blocked')['success'] is False


def test_parse_user_info_invalid_json():
	assert parse_user_info_response(200, 'not json')['success'] is False


def test_parse_user_info_includes_gift_quota_in_balance():
	# Gemai / 哈基米这类分支把充值额度放 quota、赠送额度放 gift_quota，
	# 站点钱包展示的是两者之和；只读 quota 会把余额严重低报。
	body = json.dumps(
		{
			'success': True,
			'data': {'quota': 70464, 'gift_quota': 121430385, 'total_quota': 121500849, 'used_quota': 197500000},
		}
	)

	info = parse_user_info_response(200, body)

	assert info['success'] is True
	assert info['quota'] == 243.0
	assert info['used_quota'] == 395.0


def test_parse_user_info_without_gift_quota_is_unchanged():
	body = json.dumps({'success': True, 'data': {'quota': 500000, 'used_quota': 250000}})

	info = parse_user_info_response(200, body)

	assert info['quota'] == 1.0
	assert info['used_quota'] == 0.5
