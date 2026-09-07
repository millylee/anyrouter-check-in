from pathlib import Path

WORKFLOW = Path(__file__).parent.parent / '.github' / 'workflows' / 'checkin.yml'


def test_checkin_workflow_runs_four_times_daily_at_beijing_07_past():
	text = WORKFLOW.read_text(encoding='utf-8')

	assert "- cron: '7 1,7,13,19 * * *'" in text
	assert 'workflow_dispatch:' not in text
	assert 'NOTIFY_EVERY_RUN: true' in text


def test_removed_fate_secret_is_not_wired_into_workflow():
	text = WORKFLOW.read_text(encoding='utf-8')

	assert 'EXTRA_ACCOUNTS_24' not in text


def test_removed_account_secrets_are_not_wired_into_workflow():
	text = WORKFLOW.read_text(encoding='utf-8')

	assert 'EXTRA_ACCOUNTS_3: ${{ secrets.EXTRA_ACCOUNTS_3 }}' in text
	assert 'EXTRA_ACCOUNTS_33: ${{ secrets.EXTRA_ACCOUNTS_33 }}' in text
	for removed_slot in (2, 15, 17, 18, 27, 28, 29, 30, 31, 32):
		# 用完整赋值行比对，否则 EXTRA_ACCOUNTS_2 会被 EXTRA_ACCOUNTS_20 之类的前缀误判。
		assert f'EXTRA_ACCOUNTS_{removed_slot}: ' not in text


def test_gemai_secret_is_wired_into_workflow():
	text = WORKFLOW.read_text(encoding='utf-8')

	assert 'EXTRA_ACCOUNTS_34: ${{ secrets.EXTRA_ACCOUNTS_34 }}' in text
