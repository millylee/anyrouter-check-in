from unittest.mock import MagicMock, patch
import pytest
import httpx

from utils.config import AccountConfig, AppConfig
from checkin import run_agentrouter_oauth_checkin


@pytest.mark.asyncio
async def test_run_agentrouter_oauth_checkin_success_with_reward():
	acc = AccountConfig(
		cookies={},
		api_user="12345",
		provider="agentrouter",
		name="test_gh_user",
		github_session="valid_github_user_session",
	)
	app_config = AppConfig.load_from_env()
	provider_config = app_config.get_provider("agentrouter")

	with patch("utils.oauth_agentrouter.AgentRouterOAuthClient.fetch_oauth_state") as mock_state, \
		 patch("utils.oauth_agentrouter.AgentRouterOAuthClient.authorize_github") as mock_auth, \
		 patch("utils.oauth_agentrouter.AgentRouterOAuthClient.callback_login") as mock_cb, \
		 patch("checkin.get_user_info") as mock_user_info:

		mock_state.return_value = "mock_state_123"
		mock_auth.return_value = "mock_code_456"
		mock_cb.return_value = (
			True,
			{"id": 12345, "username": "gh_user", "quota": 50000000, "checked_in": True},
			True,
			"登录成功",
		)
		mock_user_info.side_effect = [
			{"success": True, "quota": 25.0, "used_quota": 5.0, "display": "Balance: $25.0"},
			{"success": True, "quota": 50.0, "used_quota": 5.0, "display": "Balance: $50.0"},
		]

		success, before, after = await run_agentrouter_oauth_checkin({"acw_tc": "test"}, acc, "test_gh_user", provider_config)
		assert success is True
		assert before["quota"] == 25.0
		assert after["quota"] == 50.0


@pytest.mark.asyncio
async def test_run_agentrouter_oauth_checkin_already_checked_in():
	acc = AccountConfig(
		cookies={},
		api_user="12345",
		provider="agentrouter",
		name="test_gh_user",
		github_session="valid_github_user_session",
	)
	app_config = AppConfig.load_from_env()
	provider_config = app_config.get_provider("agentrouter")

	with patch("utils.oauth_agentrouter.AgentRouterOAuthClient.fetch_oauth_state") as mock_state, \
		 patch("utils.oauth_agentrouter.AgentRouterOAuthClient.authorize_github") as mock_auth, \
		 patch("utils.oauth_agentrouter.AgentRouterOAuthClient.callback_login") as mock_cb, \
		 patch("checkin.get_user_info") as mock_user_info:

		mock_state.return_value = "mock_state_123"
		mock_auth.return_value = "mock_code_456"
		mock_cb.return_value = (
			True,
			{"id": 12345, "username": "gh_user", "quota": 50000000, "checked_in": False},
			False,
			"登录成功",
		)
		mock_user_info.side_effect = [
			{"success": True, "quota": 50.0, "used_quota": 5.0, "display": "Balance: $50.0"},
			{"success": True, "quota": 50.0, "used_quota": 5.0, "display": "Balance: $50.0"},
		]

		success, before, after = await run_agentrouter_oauth_checkin({"acw_tc": "test"}, acc, "test_gh_user", provider_config)
		assert success is True
		assert before["quota"] == after["quota"]


@pytest.mark.asyncio
async def test_run_agentrouter_oauth_checkin_auth_failed():
	acc = AccountConfig(
		cookies={},
		api_user="12345",
		provider="agentrouter",
		name="test_gh_user",
		github_session="expired_session",
	)
	app_config = AppConfig.load_from_env()
	provider_config = app_config.get_provider("agentrouter")

	with patch("utils.oauth_agentrouter.AgentRouterOAuthClient.fetch_oauth_state") as mock_state, \
		 patch("utils.oauth_agentrouter.AgentRouterOAuthClient.authorize_github") as mock_auth, \
		 patch("checkin.get_user_info") as mock_user_info:

		mock_state.return_value = "mock_state_123"
		mock_auth.side_effect = RuntimeError("GitHub 登录态无效或已过期")
		mock_user_info.return_value = {"success": True, "quota": 50.0, "used_quota": 5.0, "display": "Balance: $50.0"}

		success, before, after = await run_agentrouter_oauth_checkin({"acw_tc": "test"}, acc, "test_gh_user", provider_config)
		assert success is False
