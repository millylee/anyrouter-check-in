import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestNotificationSending:
	"""测试通知发送功能"""

	@pytest.mark.parametrize('platform,method_name,env_config,error_message', [
		('email', 'send_email', {}, '未配置邮箱信息'),
		('pushplus', 'send_pushplus', {}, '未配置PushPlus Token'),
		('serverpush', 'send_serverpush', {}, '未配置Server Push key'),
		('dingtalk', 'send_dingtalk', {}, '未配置钉钉 Webhook'),
		('feishu', 'send_feishu', {}, '未配置飞书 Webhook'),
		('wecom', 'send_wecom', {}, '未配置企业微信 Webhook'),
	])
	def test_send_without_config_raises_error(
		self,
		monkeypatch,
		platform,
		method_name,
		env_config,
		error_message
	):
		"""测试无配置时发送抛出异常"""
		# 清空所有配置相关环境变量
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or any(x in key for x in ['EMAIL', 'WEBHOOK', 'TOKEN', 'KEY']):
				monkeypatch.delenv(key, raising=False)

		from notify import NotificationKit
		kit = NotificationKit()

		with pytest.raises(ValueError, match=error_message):
			getattr(kit, method_name)('测试标题', '测试内容')

	@patch('smtplib.SMTP_SSL')
	def test_email_sending_with_mock(self, mock_smtp, monkeypatch):
		"""测试邮箱发送逻辑（使用 mock）"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'EMAIL' in key or 'NOTIF_CONFIG' in key:
				monkeypatch.delenv(key, raising=False)

		# 设置邮箱配置
		monkeypatch.setenv('EMAIL_USER', 'test@example.com')
		monkeypatch.setenv('EMAIL_PASS', 'testpass')
		monkeypatch.setenv('EMAIL_TO', 'recipient@example.com')

		mock_server = MagicMock()
		mock_smtp.return_value.__enter__.return_value = mock_server

		from notify import NotificationKit
		kit = NotificationKit()
		kit.send_email('测试标题', '测试内容')

		assert mock_server.login.called
		assert mock_server.send_message.called

	@pytest.mark.parametrize('platform,method_name,env_key,env_value', [
		('pushplus', 'send_pushplus', 'PUSHPLUS_TOKEN', 'test_token'),
		('serverpush', 'send_serverpush', 'SERVERPUSHKEY', 'test_key'),
		('dingtalk', 'send_dingtalk', 'DINGDING_WEBHOOK', 'https://example.com/webhook'),
		('feishu', 'send_feishu', 'FEISHU_WEBHOOK', 'https://example.com/webhook'),
		('wecom', 'send_wecom', 'WEIXIN_WEBHOOK', 'https://example.com/webhook'),
	])
	@patch('httpx.Client')
	def test_http_platforms_sending_with_mock(
		self,
		mock_client,
		monkeypatch,
		platform,
		method_name,
		env_key,
		env_value
	):
		"""测试各 HTTP 平台的发送逻辑（使用 mock）"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or any(x in key for x in ['WEBHOOK', 'TOKEN', 'KEY']):
				monkeypatch.delenv(key, raising=False)

		monkeypatch.setenv(env_key, env_value)

		mock_client_instance = MagicMock()
		mock_client.return_value.__enter__.return_value = mock_client_instance

		from notify import NotificationKit
		kit = NotificationKit()
		getattr(kit, method_name)('测试标题', '测试内容')

		mock_client_instance.post.assert_called_once()

	@pytest.mark.parametrize('use_card,color_theme', [
		(True, 'red'),
		(True, 'blue'),
		(False, None),
	])
	@patch('httpx.Client')
	def test_feishu_card_modes(self, mock_client, monkeypatch, use_card, color_theme):
		"""测试飞书的卡片模式和普通模式"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'FEISHU' in key or 'NOTIF_CONFIG' in key:
				monkeypatch.delenv(key, raising=False)

		# 构造配置
		config = {
			'webhook': 'https://example.com/webhook',
			'platform_settings': {
				'use_card': use_card
			},
			'template': None
		}

		if use_card and color_theme:
			config['platform_settings']['color_theme'] = color_theme

		monkeypatch.setenv('FEISHU_NOTIF_CONFIG', json.dumps(config))

		mock_client_instance = MagicMock()
		mock_client.return_value.__enter__.return_value = mock_client_instance

		from notify import NotificationKit
		kit = NotificationKit()
		kit.send_feishu('测试标题', '测试内容')

		# 验证调用了 post 方法
		assert mock_client_instance.post.called
		call_args = mock_client_instance.post.call_args
		data = call_args[1]['json']

		if use_card:
			# 验证是卡片模式
			assert data['msg_type'] == 'interactive'
			assert 'card' in data
			if color_theme:
				assert data['card']['header']['template'] == color_theme
		else:
			# 验证是文本模式
			assert data['msg_type'] == 'text'
			assert 'text' in data

	@pytest.mark.parametrize('markdown_style,expected_msgtype', [
		('markdown', 'markdown'),
		('markdown_v2', 'markdown_v2'),
		(None, 'text'),
		('invalid', 'text'),
	])
	@patch('httpx.Client')
	def test_wecom_markdown_style_modes(self, mock_client, monkeypatch, markdown_style, expected_msgtype):
		"""测试企业微信的 markdown_style 配置"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'WECOM' in key or 'WEIXIN' in key or 'NOTIF_CONFIG' in key:
				monkeypatch.delenv(key, raising=False)

		# 构造配置
		config = {
			'webhook': 'https://example.com/webhook',
			'platform_settings': {
				'markdown_style': markdown_style
			},
			'template': None
		}

		monkeypatch.setenv('WECOM_NOTIF_CONFIG', json.dumps(config))

		mock_client_instance = MagicMock()
		mock_client.return_value.__enter__.return_value = mock_client_instance

		from notify import NotificationKit
		kit = NotificationKit()
		kit.send_wecom('测试标题', '测试内容')

		# 验证调用了 post 方法
		assert mock_client_instance.post.called
		call_args = mock_client_instance.post.call_args
		data = call_args[1]['json']

		# 验证消息格式
		assert data['msgtype'] == expected_msgtype
		if 'markdown' in expected_msgtype:
			assert 'markdown' in data
			assert '**测试标题**' in data['markdown']['content']
		else:
			assert 'text' in data
