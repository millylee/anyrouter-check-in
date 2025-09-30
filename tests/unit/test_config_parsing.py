import json
import os

import pytest


class TestConfigParsing:
	"""测试配置解析功能"""

	def test_no_config_returns_none(self, monkeypatch):
		"""测试无配置时所有配置为 None"""
		# 清空所有相关环境变量
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or key in ['EMAIL_USER', 'WEIXIN_WEBHOOK', 'DINGDING_WEBHOOK', 'FEISHU_WEBHOOK', 'PUSHPLUS_TOKEN', 'SERVERPUSHKEY']:
				monkeypatch.delenv(key, raising=False)

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.email_config is None
		assert kit.dingtalk_config is None
		assert kit.feishu_config is None
		assert kit.wecom_config is None
		assert kit.pushplus_config is None
		assert kit.serverpush_config is None

	@pytest.mark.parametrize('config_format,has_template,template_value', [
		('json_with_custom_template', True, 'custom template content'),
		('json_with_null_template', False, None),
		('json_without_template_key', False, None),
	])
	def test_wecom_config_formats(self, monkeypatch, config_format, has_template, template_value):
		"""测试企业微信配置的各种格式"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'WEBHOOK' in key:
				monkeypatch.delenv(key, raising=False)

		# 构造配置
		if config_format == 'json_with_custom_template':
			config = {'webhook': 'https://example.com/webhook', 'template': template_value}
		elif config_format == 'json_with_null_template':
			config = {'webhook': 'https://example.com/webhook', 'template': None}
		else:  # json_without_template_key
			config = {'webhook': 'https://example.com/webhook'}

		monkeypatch.setenv('WECOM_NOTIF_CONFIG', json.dumps(config))

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.wecom_config is not None
		assert kit.wecom_config.webhook == 'https://example.com/webhook'

		# 验证模板处理
		if has_template:
			assert kit.wecom_config.template == template_value
		else:
			# template 为 null 或不存在时，应该加载默认模板
			assert kit.wecom_config.template is not None
			assert len(kit.wecom_config.template) > 0

	@pytest.mark.parametrize('config_format,webhook_value', [
		('old_format_string', 'https://example.com/webhook'),
	])
	def test_wecom_old_format_loads_default_template(self, monkeypatch, config_format, webhook_value):
		"""测试企业微信旧格式配置（字符串形式）加载默认模板"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'WEBHOOK' in key:
				monkeypatch.delenv(key, raising=False)

		monkeypatch.setenv('WEIXIN_WEBHOOK', webhook_value)

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.wecom_config is not None
		assert kit.wecom_config.webhook == webhook_value
		assert kit.wecom_config.template is not None
		assert len(kit.wecom_config.template) > 0

	@pytest.mark.parametrize('platform,env_key,config_value,expected_webhook', [
		('dingtalk', 'DINGTALK_NOTIF_CONFIG', {'webhook': 'https://dingtalk.com/webhook', 'template': 'custom'}, 'https://dingtalk.com/webhook'),
		('dingtalk', 'DINGTALK_NOTIF_CONFIG', {'webhook': 'https://dingtalk.com/webhook', 'template': None}, 'https://dingtalk.com/webhook'),
		('feishu', 'FEISHU_NOTIF_CONFIG', {'webhook': 'https://feishu.com/webhook', 'template': 'custom'}, 'https://feishu.com/webhook'),
		('feishu', 'FEISHU_NOTIF_CONFIG', {'webhook': 'https://feishu.com/webhook', 'template': None}, 'https://feishu.com/webhook'),
	])
	def test_webhook_platforms_json_config(
		self,
		monkeypatch,
		platform,
		env_key,
		config_value,
		expected_webhook
	):
		"""测试钉钉、飞书等 webhook 平台的 JSON 配置"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'WEBHOOK' in key:
				monkeypatch.delenv(key, raising=False)

		monkeypatch.setenv(env_key, json.dumps(config_value))

		from notify import NotificationKit
		kit = NotificationKit()

		config_attr = f'{platform}_config'
		config = getattr(kit, config_attr)

		assert config is not None
		assert config.webhook == expected_webhook

		# 验证模板
		if config_value.get('template') is None:
			assert config.template is not None
			assert len(config.template) > 0
		else:
			assert config.template == config_value['template']

	@pytest.mark.parametrize('platform,env_key,webhook_value', [
		('dingtalk', 'DINGDING_WEBHOOK', 'https://dingtalk.com/webhook'),
		('feishu', 'FEISHU_WEBHOOK', 'https://feishu.com/webhook'),
	])
	def test_webhook_platforms_old_format(self, monkeypatch, platform, env_key, webhook_value):
		"""测试钉钉、飞书旧格式配置（字符串）"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'WEBHOOK' in key:
				monkeypatch.delenv(key, raising=False)

		monkeypatch.setenv(env_key, webhook_value)

		from notify import NotificationKit
		kit = NotificationKit()

		config_attr = f'{platform}_config'
		config = getattr(kit, config_attr)

		assert config is not None
		assert config.webhook == webhook_value
		assert config.template is not None
		assert len(config.template) > 0

	@pytest.mark.parametrize('config_format,has_template', [
		('json_with_custom_template', True),
		('json_with_null_template', False),
	])
	def test_pushplus_config_formats(self, monkeypatch, config_format, has_template):
		"""测试 PushPlus 配置的各种格式"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'PUSHPLUS' in key:
				monkeypatch.delenv(key, raising=False)

		# 构造配置
		if config_format == 'json_with_custom_template':
			config = {'token': 'test_token_123', 'template': 'custom pushplus template'}
		else:  # json_with_null_template
			config = {'token': 'test_token_123', 'template': None}

		monkeypatch.setenv('PUSHPLUS_NOTIF_CONFIG', json.dumps(config))

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.pushplus_config is not None
		assert kit.pushplus_config.token == 'test_token_123'

		if has_template:
			assert kit.pushplus_config.template == 'custom pushplus template'
		else:
			assert kit.pushplus_config.template is not None
			assert len(kit.pushplus_config.template) > 0

	def test_pushplus_old_format(self, monkeypatch):
		"""测试 PushPlus 旧格式配置"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'PUSHPLUS' in key:
				monkeypatch.delenv(key, raising=False)

		monkeypatch.setenv('PUSHPLUS_TOKEN', 'old_format_token')

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.pushplus_config is not None
		assert kit.pushplus_config.token == 'old_format_token'
		assert kit.pushplus_config.template is not None
		assert len(kit.pushplus_config.template) > 0

	@pytest.mark.parametrize('config_format,has_template', [
		('json_with_custom_template', True),
		('json_with_null_template', False),
	])
	def test_serverpush_config_formats(self, monkeypatch, config_format, has_template):
		"""测试 Server 酱配置的各种格式"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'SERVERPUSH' in key:
				monkeypatch.delenv(key, raising=False)

		# 构造配置
		if config_format == 'json_with_custom_template':
			config = {'send_key': 'test_send_key', 'template': 'custom serverpush template'}
		else:  # json_with_null_template
			config = {'send_key': 'test_send_key', 'template': None}

		monkeypatch.setenv('SERVERPUSH_NOTIF_CONFIG', json.dumps(config))

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.serverpush_config is not None
		assert kit.serverpush_config.send_key == 'test_send_key'

		if has_template:
			assert kit.serverpush_config.template == 'custom serverpush template'
		else:
			assert kit.serverpush_config.template is not None
			assert len(kit.serverpush_config.template) > 0

	def test_serverpush_old_format(self, monkeypatch):
		"""测试 Server 酱旧格式配置"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'SERVERPUSH' in key:
				monkeypatch.delenv(key, raising=False)

		monkeypatch.setenv('SERVERPUSHKEY', 'old_format_key')

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.serverpush_config is not None
		assert kit.serverpush_config.send_key == 'old_format_key'
		assert kit.serverpush_config.template is not None
		assert len(kit.serverpush_config.template) > 0

	@pytest.mark.parametrize('config_format,has_template', [
		('json_with_custom_template', True),
		('json_with_null_template', False),
	])
	def test_email_config_formats(self, monkeypatch, config_format, has_template):
		"""测试邮箱配置的各种格式"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'EMAIL' in key:
				monkeypatch.delenv(key, raising=False)

		# 构造配置
		if config_format == 'json_with_custom_template':
			config = {
				'user': 'test@example.com',
				'pass': 'test_password',
				'to': 'recipient@example.com',
				'template': 'custom email template'
			}
		else:  # json_with_null_template
			config = {
				'user': 'test@example.com',
				'pass': 'test_password',
				'to': 'recipient@example.com',
				'template': None
			}

		monkeypatch.setenv('EMAIL_NOTIF_CONFIG', json.dumps(config))

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.email_config is not None
		assert kit.email_config.user == 'test@example.com'
		assert kit.email_config.password == 'test_password'
		assert kit.email_config.to == 'recipient@example.com'

		if has_template:
			assert kit.email_config.template == 'custom email template'
		else:
			assert kit.email_config.template is not None
			assert len(kit.email_config.template) > 0

	def test_email_old_format(self, monkeypatch):
		"""测试邮箱旧格式配置"""
		# 清空环境
		for key in list(os.environ.keys()):
			if 'NOTIF_CONFIG' in key or 'EMAIL' in key:
				monkeypatch.delenv(key, raising=False)

		monkeypatch.setenv('EMAIL_USER', 'old@example.com')
		monkeypatch.setenv('EMAIL_PASS', 'old_password')
		monkeypatch.setenv('EMAIL_TO', 'old_recipient@example.com')

		from notify import NotificationKit
		kit = NotificationKit()

		assert kit.email_config is not None
		assert kit.email_config.user == 'old@example.com'
		assert kit.email_config.password == 'old_password'
		assert kit.email_config.to == 'old_recipient@example.com'
		assert kit.email_config.template is not None
		assert len(kit.email_config.template) > 0
