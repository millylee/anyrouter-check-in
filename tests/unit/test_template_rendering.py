import json
from pathlib import Path

import pytest


project_root = Path(__file__).parent.parent.parent


class TestTemplateRendering:
	"""测试模板渲染功能"""

	@pytest.fixture
	def notification_kit(self):
		"""创建不依赖环境变量的 NotificationKit 实例"""
		from notify import NotificationKit
		return NotificationKit()

	@pytest.fixture
	def single_success_data(self):
		"""单账号成功的测试数据"""
		from models import NotificationData, AccountResult, NotificationStats

		return NotificationData(
			accounts=[
				AccountResult(
					name='Account-1',
					status='success',
					quota=25.0,
					used=5.0,
					error=None
				)
			],
			stats=NotificationStats(success_count=1, failed_count=0, total_count=1),
			timestamp='2024-01-01 12:00:00'
		)

	@pytest.fixture
	def single_failure_data(self):
		"""单账号失败的测试数据"""
		from models import NotificationData, AccountResult, NotificationStats

		return NotificationData(
			accounts=[
				AccountResult(
					name='Account-1',
					status='failed',
					quota=None,
					used=None,
					error='Connection timeout'
				)
			],
			stats=NotificationStats(success_count=0, failed_count=1, total_count=1),
			timestamp='2024-01-01 12:00:00'
		)

	@pytest.fixture
	def multiple_mixed_data(self):
		"""多账号混合的测试数据"""
		from models import NotificationData, AccountResult, NotificationStats

		return NotificationData(
			accounts=[
				AccountResult(name='Account-1', status='success', quota=25.0, used=5.0, error=None),
				AccountResult(name='Account-2', status='success', quota=30.0, used=10.0, error=None),
				AccountResult(name='Account-3', status='failed', quota=None, used=None, error='Authentication failed')
			],
			stats=NotificationStats(success_count=2, failed_count=1, total_count=3),
			timestamp='2024-01-01 12:00:00'
		)

	@pytest.mark.parametrize('platform,template_file', [
		('dingtalk', 'dingtalk.json'),
		('email', 'email.json'),
		('pushplus', 'pushplus.json'),
		('serverpush', 'serverpush.json'),
	])
	def test_default_template_single_success(
		self,
		notification_kit,
		single_success_data,
		platform,
		template_file
	):
		"""测试默认模板渲染单账号成功场景"""
		config_path = project_root / 'notif_config' / template_file
		with open(config_path) as f:
			config = json.load(f)

		result = notification_kit._render_template(config['template'], single_success_data)

		assert '[TIME] Execution time: 2024-01-01 12:00:00' in result
		assert '[BALANCE] Account-1' in result
		assert ':money: Current balance: $25.0, Used: $5.0' in result
		assert '[STATS] Check-in result statistics:' in result
		assert '[SUCCESS] Success: 1/1' in result
		assert '[FAIL] Failed: 0/1' in result
		assert '[SUCCESS] All accounts check-in successful!' in result

	def test_wecom_default_template_single_success(self, notification_kit, single_success_data):
		"""测试企业微信默认模板渲染单账号成功场景（Markdown 格式）"""
		config_path = project_root / 'notif_config' / 'wecom.json'
		with open(config_path) as f:
			config = json.load(f)

		result = notification_kit._render_template(config['template'], single_success_data)

		assert '**[TIME] Execution time:** 2024-01-01 12:00:00' in result
		assert '**[BALANCE] Account-1**' in result
		assert ':money: Current balance: $25.0, Used: $5.0' in result
		assert '**[STATS] Check-in result statistics:**' in result
		assert '**[SUCCESS] Success:** 1/1' in result
		assert '**[FAIL] Failed:** 0/1' in result
		assert '**[SUCCESS] All accounts check-in successful!**' in result

	def test_feishu_default_template_single_success(self, notification_kit, single_success_data):
		"""测试飞书默认模板渲染单账号成功场景（Markdown 格式）"""
		config_path = project_root / 'notif_config' / 'feishu.json'
		with open(config_path) as f:
			config = json.load(f)

		result = notification_kit._render_template(config['template'], single_success_data)

		assert '**[TIME] Execution time:** 2024-01-01 12:00:00' in result
		assert '**[BALANCE] Account-1**' in result
		assert ':money: Current balance: $25.0, Used: $5.0' in result
		assert '**[STATS] Check-in result statistics:**' in result
		assert '**[SUCCESS] Success:** 1/1' in result
		assert '**[FAIL] Failed:** 0/1' in result
		assert '**[SUCCESS] All accounts check-in successful!**' in result

	@pytest.mark.parametrize('platform,template_file', [
		('dingtalk', 'dingtalk.json'),
	])
	def test_default_template_single_failure(
		self,
		notification_kit,
		single_failure_data,
		platform,
		template_file
	):
		"""测试默认模板渲染单账号失败场景"""
		config_path = project_root / 'notif_config' / template_file
		with open(config_path) as f:
			config = json.load(f)

		result = notification_kit._render_template(config['template'], single_failure_data)

		assert '[TIME] Execution time: 2024-01-01 12:00:00' in result
		assert '[FAIL] Account-1 exception: Connection timeout' in result
		assert '[STATS] Check-in result statistics:' in result
		assert '[SUCCESS] Success: 0/1' in result
		assert '[FAIL] Failed: 1/1' in result
		assert '[ERROR] All accounts check-in failed' in result

	def test_wecom_default_template_single_failure(self, notification_kit, single_failure_data):
		"""测试企业微信默认模板渲染单账号失败场景（Markdown 格式）"""
		config_path = project_root / 'notif_config' / 'wecom.json'
		with open(config_path) as f:
			config = json.load(f)

		result = notification_kit._render_template(config['template'], single_failure_data)

		assert '**[TIME] Execution time:** 2024-01-01 12:00:00' in result
		assert '**[FAIL] Account-1 exception:** Connection timeout' in result
		assert '**[STATS] Check-in result statistics:**' in result
		assert '**[SUCCESS] Success:** 0/1' in result
		assert '**[FAIL] Failed:** 1/1' in result
		assert '**[ERROR] All accounts check-in failed**' in result

	@pytest.mark.parametrize('platform,template_file', [
		('dingtalk', 'dingtalk.json'),
	])
	def test_default_template_multiple_mixed(
		self,
		notification_kit,
		multiple_mixed_data,
		platform,
		template_file
	):
		"""测试默认模板渲染多账号混合场景"""
		config_path = project_root / 'notif_config' / template_file
		with open(config_path) as f:
			config = json.load(f)

		result = notification_kit._render_template(config['template'], multiple_mixed_data)

		assert '[TIME] Execution time: 2024-01-01 12:00:00' in result
		assert '[BALANCE] Account-1' in result
		assert ':money: Current balance: $25.0, Used: $5.0' in result
		assert '[BALANCE] Account-2' in result
		assert ':money: Current balance: $30.0, Used: $10.0' in result
		assert '[FAIL] Account-3 exception: Authentication failed' in result
		assert '[STATS] Check-in result statistics:' in result
		assert '[SUCCESS] Success: 2/3' in result
		assert '[FAIL] Failed: 1/3' in result
		assert '[WARN] Some accounts check-in successful' in result

	def test_wecom_default_template_multiple_mixed(self, notification_kit, multiple_mixed_data):
		"""测试企业微信默认模板渲染多账号混合场景（Markdown 格式）"""
		config_path = project_root / 'notif_config' / 'wecom.json'
		with open(config_path) as f:
			config = json.load(f)

		result = notification_kit._render_template(config['template'], multiple_mixed_data)

		assert '**[TIME] Execution time:** 2024-01-01 12:00:00' in result
		assert '**[BALANCE] Account-1**' in result
		assert ':money: Current balance: $25.0, Used: $5.0' in result
		assert '**[BALANCE] Account-2**' in result
		assert ':money: Current balance: $30.0, Used: $10.0' in result
		assert '**[FAIL] Account-3 exception:** Authentication failed' in result
		assert '**[STATS] Check-in result statistics:**' in result
		assert '**[SUCCESS] Success:** 2/3' in result
		assert '**[FAIL] Failed:** 1/3' in result
		assert '**[WARN] Some accounts check-in successful**' in result

	def test_custom_template_with_variables(self, notification_kit, single_success_data):
		"""测试自定义模板的变量访问"""
		template = '{{ timestamp }} - {% for account in accounts %}{{ account.name }}: {{ account.status }}{% endfor %} - 成功: {{ stats.success_count }}/{{ stats.total_count }}'
		result = notification_kit._render_template(template, single_success_data)

		assert '2024-01-01 12:00:00' in result
		assert 'Account-1' in result
		assert 'success' in result
		assert '1/1' in result

	def test_custom_template_with_convenience_flags(self, notification_kit):
		"""测试自定义模板使用便利标志（all_success, all_failed, partial_success）"""
		from models import NotificationData, AccountResult, NotificationStats

		template = '{% if all_success %}ALL SUCCESS{% endif %}{% if all_failed %}ALL FAILED{% endif %}{% if partial_success %}PARTIAL{% endif %}'

		# 测试 all_success
		data_all_success = NotificationData(
			accounts=[AccountResult(name='A1', status='success', quota=25.0, used=5.0, error=None)],
			stats=NotificationStats(success_count=1, failed_count=0, total_count=1),
			timestamp='2024-01-01 12:00:00'
		)
		result = notification_kit._render_template(template, data_all_success)
		assert 'ALL SUCCESS' in result

		# 测试 all_failed
		data_all_failed = NotificationData(
			accounts=[AccountResult(name='A1', status='failed', quota=None, used=None, error='Error')],
			stats=NotificationStats(success_count=0, failed_count=1, total_count=1),
			timestamp='2024-01-01 12:00:00'
		)
		result = notification_kit._render_template(template, data_all_failed)
		assert 'ALL FAILED' in result

		# 测试 partial_success
		data_partial = NotificationData(
			accounts=[
				AccountResult(name='A1', status='success', quota=25.0, used=5.0, error=None),
				AccountResult(name='A2', status='failed', quota=None, used=None, error='Error')
			],
			stats=NotificationStats(success_count=1, failed_count=1, total_count=2),
			timestamp='2024-01-01 12:00:00'
		)
		result = notification_kit._render_template(template, data_partial)
		assert 'PARTIAL' in result

	def test_invalid_template_fallback(self, notification_kit, single_success_data):
		"""测试无效模板语法时的回退处理"""
		# 使用会触发解析错误的模板语法
		invalid_template = '{% if unclosed_block %}'
		result = notification_kit._render_template(invalid_template, single_success_data)

		# 应该返回回退格式
		assert '2024-01-01 12:00:00' in result
		assert 'Account-1' in result
