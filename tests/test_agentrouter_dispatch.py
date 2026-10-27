from unittest.mock import MagicMock, patch
import pytest

from utils.config import AccountConfig, AppConfig
from checkin import check_in_account


def test_account_config_supports_oauth_sessions():
	data = {
		"name": "test_github",
		"provider": "agentrouter",
		"github_session": "gh_token_123",
	}
	acc = AccountConfig.from_dict(data, 0)
	assert acc.github_session == "gh_token_123"
	assert acc.has_oauth_session() is True


def test_account_config_extracts_oauth_from_cookies_dict():
	data = {
		"name": "test_gh_in_cookies",
		"provider": "agentrouter",
		"cookies": {"user_session": "cookie_user_session_val"},
	}
	acc = AccountConfig.from_dict(data, 0)
	assert acc.github_session == "cookie_user_session_val"
	assert acc.has_oauth_session() is True


@pytest.mark.asyncio
async def test_agentrouter_static_session_warns_and_does_not_fake_success():
	acc = AccountConfig(
		cookies={"session": "stale_session_value"},
		api_user="12345",
		provider="agentrouter",
		name="test_static_acc",
	)
	app_config = AppConfig.load_from_env()

	with patch("checkin.get_user_info") as mock_get_user_info:
		mock_get_user_info.return_value = {
			"success": True,
			"quota": 100.0,
			"used_quota": 20.0,
			"display": "Current balance: $100.0, Used: $20.0",
		}

		success, before, after = await check_in_account(acc, 0, app_config)
		assert success is False

def test_load_accounts_config_accepts_oauth_without_api_user(monkeypatch):
	import json
	from utils.config import load_accounts_config
	payload = json.dumps([
		{"name": "gh_user", "provider": "agentrouter", "github_session": "token123"}
	])
	monkeypatch.setenv("ANYROUTER_ACCOUNTS", payload)
	accounts = load_accounts_config()
	assert accounts is not None
	assert len(accounts) == 1
	assert accounts[0].github_session == "token123"
	assert accounts[0].api_user is None
