import asyncio
import sys
from pathlib import Path

import pytest

# 添加项目根目录到 PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.config import AccountConfig, AppConfig

import checkin


@pytest.fixture(autouse=True)
def mock_balance_file(monkeypatch):
	monkeypatch.setattr(checkin, 'load_balance_hash', lambda: 'old_hash')
	monkeypatch.setattr(checkin, 'save_balance_hash', lambda balance_hash: None)


@pytest.fixture
def accounts():
	return [
		AccountConfig(cookies='session=ok', api_user='user-1', name='Success Account'),
		AccountConfig(cookies='session=bad', api_user='user-2', name='Failed Account'),
	]


def test_success_notification_disabled_excludes_balance_change_content(monkeypatch, accounts):
	"""NOTIFY_ON_SUCCESS=false 时，余额变化内容不能搭失败通知一起发出。"""

	async def fake_check_in_account(account, index, app_config):
		if index == 0:
			return (
				True,
				{'success': True, 'quota': 10.0, 'used_quota': 1.0},
				{'success': True, 'quota': 20.0, 'used_quota': 1.0, 'display': 'success balance'},
			)
		return (
			False,
			{'success': True, 'quota': 5.0, 'used_quota': 1.0},
			{'success': False, 'error': 'check-in failed'},
		)

	push_calls = []

	monkeypatch.setattr(checkin.AppConfig, 'load_from_env', lambda: AppConfig(providers={}, notify_on_success=False))
	monkeypatch.setattr(checkin, 'load_accounts_config', lambda: accounts)
	monkeypatch.setattr(checkin, 'check_in_account', fake_check_in_account)
	monkeypatch.setattr(checkin.notify, 'push_message', lambda *args, **kwargs: push_calls.append((args, kwargs)))

	with pytest.raises(SystemExit) as exc_info:
		asyncio.run(checkin.main())

	assert exc_info.value.code == 0
	assert len(push_calls) == 1
	notify_content = push_calls[0][0][1]
	assert 'Failed Account' in notify_content
	assert 'Success Account' not in notify_content
	assert '[CHECK-IN]' not in notify_content


def test_failure_notification_disabled_excludes_exception_content(monkeypatch, accounts):
	"""NOTIFY_ON_FAILURE=false 时，异常内容不能搭成功通知一起发出。"""

	async def fake_check_in_account(account, index, app_config):
		if index == 0:
			return (
				True,
				{'success': True, 'quota': 10.0, 'used_quota': 1.0},
				{'success': True, 'quota': 20.0, 'used_quota': 1.0, 'display': 'success balance'},
			)
		raise RuntimeError('network exploded')

	push_calls = []

	monkeypatch.setattr(checkin.AppConfig, 'load_from_env', lambda: AppConfig(providers={}, notify_on_failure=False))
	monkeypatch.setattr(checkin, 'load_accounts_config', lambda: accounts)
	monkeypatch.setattr(checkin, 'check_in_account', fake_check_in_account)
	monkeypatch.setattr(checkin.notify, 'push_message', lambda *args, **kwargs: push_calls.append((args, kwargs)))

	with pytest.raises(SystemExit) as exc_info:
		asyncio.run(checkin.main())

	assert exc_info.value.code == 0
	assert len(push_calls) == 1
	notify_content = push_calls[0][0][1]
	assert 'Success Account' in notify_content
	assert 'Failed Account exception' not in notify_content
	assert 'network exploded' not in notify_content


def test_all_notifications_disabled_skips_push(monkeypatch, accounts):
	async def fake_check_in_account(account, index, app_config):
		if index == 0:
			return (
				True,
				{'success': True, 'quota': 10.0, 'used_quota': 1.0},
				{'success': True, 'quota': 20.0, 'used_quota': 1.0, 'display': 'success balance'},
			)
		return False, None, {'success': False, 'error': 'check-in failed'}

	push_calls = []

	monkeypatch.setattr(
		checkin.AppConfig,
		'load_from_env',
		lambda: AppConfig(providers={}, notify_on_failure=False, notify_on_success=False),
	)
	monkeypatch.setattr(checkin, 'load_accounts_config', lambda: accounts)
	monkeypatch.setattr(checkin, 'check_in_account', fake_check_in_account)
	monkeypatch.setattr(checkin.notify, 'push_message', lambda *args, **kwargs: push_calls.append((args, kwargs)))

	with pytest.raises(SystemExit) as exc_info:
		asyncio.run(checkin.main())

	assert exc_info.value.code == 0
	assert push_calls == []
