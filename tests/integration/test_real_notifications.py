import os
from unittest.mock import patch

import pytest


class TestIntegration:
	"""集成测试 - 测试端到端流程"""

	@pytest.fixture
	def notification_kit_from_env(self):
		"""从环境变量创建 NotificationKit 实例（用于集成测试）"""
		from notify import NotificationKit
		return NotificationKit()

	@pytest.fixture
	def test_notification_data(self):
		"""创建测试用的通知数据"""
		from models import NotificationData, AccountResult, NotificationStats

		return NotificationData(
			accounts=[
				AccountResult(
					name='测试账号',
					status='success',
					quota=25.0,
					used=5.0,
					error=None
				)
			],
			stats=NotificationStats(success_count=1, failed_count=0, total_count=1),
			timestamp='2024-01-01 12:00:00'
		)

	def test_real_notification_with_env_config(
		self,
		notification_kit_from_env,
		test_notification_data
	):
		"""
		真实接口测试 - 需要在 .env.local 文件中配置 ENABLE_REAL_TEST=true

		此测试会实际发送通知到配置的平台，用于验证端到端流程。
		"""
		if os.getenv('ENABLE_REAL_TEST') != 'true':
			pytest.skip('未启用真实接口测试。请在 .env.local 中设置 ENABLE_REAL_TEST=true')

		# 尝试发送通知
		notification_kit_from_env.push_message('集成测试消息', test_notification_data)

		# 如果没有抛出异常，则测试通过
		# 注意：这个测试不验证通知是否真的成功发送，只验证代码执行流程正确

	@patch('notify.NotificationKit._send_email_with_template')
	@patch('notify.NotificationKit._send_dingtalk_with_template')
	@patch('notify.NotificationKit._send_wecom_with_template')
	@patch('notify.NotificationKit._send_pushplus_with_template')
	@patch('notify.NotificationKit._send_feishu_with_template')
	@patch('notify.NotificationKit._send_serverpush_with_template')
	def test_push_message_routing_logic(
		self,
		mock_serverpush,
		mock_feishu,
		mock_pushplus,
		mock_wecom,
		mock_dingtalk,
		mock_email,
		notification_kit_from_env,
		test_notification_data
	):
		"""测试 push_message 的路由逻辑 - 验证根据配置调用相应平台"""
		notification_kit_from_env.push_message('测试标题', test_notification_data)

		# 验证有配置的平台被调用
		if notification_kit_from_env.email_config:
			assert mock_email.called
		else:
			assert not mock_email.called

		if notification_kit_from_env.dingtalk_config:
			assert mock_dingtalk.called
		else:
			assert not mock_dingtalk.called

		if notification_kit_from_env.wecom_config:
			assert mock_wecom.called
		else:
			assert not mock_wecom.called

		if notification_kit_from_env.pushplus_config:
			assert mock_pushplus.called
		else:
			assert not mock_pushplus.called

		if notification_kit_from_env.feishu_config:
			assert mock_feishu.called
		else:
			assert not mock_feishu.called

		if notification_kit_from_env.serverpush_config:
			assert mock_serverpush.called
		else:
			assert not mock_serverpush.called
