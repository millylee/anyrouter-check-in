import pytest


class TestNotificationDataModel:
	"""测试 NotificationData 数据模型"""

	@pytest.fixture
	def create_account_result(self):
		"""创建账号结果的工厂函数"""
		from models import AccountResult

		def _create(
			name: str = '测试账号',
			status: str = 'success',
			quota: float = 25.0,
			used: float = 5.0,
			error: str = None
		) -> AccountResult:
			return AccountResult(
				name=name,
				status=status,
				quota=quota if status == 'success' else None,
				used=used if status == 'success' else None,
				error=error if status != 'success' else None
			)

		return _create

	@pytest.fixture
	def create_notification_data(self, create_account_result):
		"""创建通知数据的工厂函数"""
		from typing import List
		from models import NotificationData, AccountResult, NotificationStats

		def _create(
			accounts: List[AccountResult],
			timestamp: str = '2024-01-01 12:00:00'
		) -> NotificationData:
			success_count = sum(1 for acc in accounts if acc.status == 'success')
			failed_count = len(accounts) - success_count

			stats = NotificationStats(
				success_count=success_count,
				failed_count=failed_count,
				total_count=len(accounts)
			)

			return NotificationData(
				accounts=accounts,
				stats=stats,
				timestamp=timestamp
			)

		return _create

	def test_all_success_property(self, create_account_result, create_notification_data):
		"""测试 all_success 属性"""
		data = create_notification_data([
			create_account_result(name='Account-1'),
			create_account_result(name='Account-2')
		])
		assert data.all_success is True
		assert data.all_failed is False
		assert data.partial_success is False

	def test_all_failed_property(self, create_account_result, create_notification_data):
		"""测试 all_failed 属性"""
		data = create_notification_data([
			create_account_result(name='Account-1', status='failed', error='Error 1'),
			create_account_result(name='Account-2', status='failed', error='Error 2')
		])
		assert data.all_success is False
		assert data.all_failed is True
		assert data.partial_success is False

	def test_partial_success_property(self, create_account_result, create_notification_data):
		"""测试 partial_success 属性"""
		data = create_notification_data([
			create_account_result(name='Account-1'),
			create_account_result(name='Account-2', status='failed', error='Error')
		])
		assert data.all_success is False
		assert data.all_failed is False
		assert data.partial_success is True
