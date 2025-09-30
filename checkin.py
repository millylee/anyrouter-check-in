#!/usr/bin/env python3
"""
AnyRouter.top 自动签到脚本
"""

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime
from typing import List

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from notify import notify
from models import NotificationData, AccountResult, NotificationStats

# 禁用变量插值以保留模板中的 $ 符号
load_dotenv(interpolate=False)

BALANCE_HASH_FILE = 'balance_hash.txt'


def load_accounts():
	"""从环境变量加载多账号配置"""
	accounts_str = os.getenv('ANYROUTER_ACCOUNTS')
	if not accounts_str:
		print('ERROR: ANYROUTER_ACCOUNTS environment variable not found')
		return None

	try:
		accounts_data = json.loads(accounts_str)

		# 检查是否为数组格式
		if not isinstance(accounts_data, list):
			print('ERROR: Account configuration must use array format [{}]')
			return None

		# 验证账号数据格式
		for i, account in enumerate(accounts_data):
			if not isinstance(account, dict):
				print(f'ERROR: Account {i + 1} configuration format is incorrect')
				return None
			if 'cookies' not in account or 'api_user' not in account:
				print(f'ERROR: Account {i + 1} missing required fields (cookies, api_user)')
				return None
			# 如果有 name 字段，确保它不是空字符串
			if 'name' in account and not account['name']:
				print(f'ERROR: Account {i + 1} name field cannot be empty')
				return None

		return accounts_data
	except Exception as e:
		print(f'ERROR: Account configuration format is incorrect: {e}')
		return None


def load_balance_hash():
	"""加载余额hash"""
	try:
		if os.path.exists(BALANCE_HASH_FILE):
			with open(BALANCE_HASH_FILE, 'r', encoding='utf-8') as f:
				return f.read().strip()
	except Exception:
		pass
	return None


def save_balance_hash(balance_hash):
	"""保存余额hash"""
	try:
		with open(BALANCE_HASH_FILE, 'w', encoding='utf-8') as f:
			f.write(balance_hash)
	except Exception as e:
		print(f'Warning: Failed to save balance hash: {e}')


def generate_balance_hash(balances):
	"""生成余额数据的hash"""
	# 将包含 quota 和 used 的结构转换为简单的 quota 值用于 hash 计算
	simple_balances = {k: v['quota'] for k, v in balances.items()} if balances else {}
	balance_json = json.dumps(simple_balances, sort_keys=True, separators=(',', ':'))
	return hashlib.sha256(balance_json.encode('utf-8')).hexdigest()[:16]


def get_account_display_name(account_info, account_index):
	"""获取账号显示名称"""
	return account_info.get('name', f'Account {account_index + 1}')


def parse_cookies(cookies_data):
	"""解析 cookies 数据"""
	if isinstance(cookies_data, dict):
		return cookies_data

	if isinstance(cookies_data, str):
		cookies_dict = {}
		for cookie in cookies_data.split(';'):
			if '=' in cookie:
				key, value = cookie.strip().split('=', 1)
				cookies_dict[key] = value
		return cookies_dict
	return {}


async def get_waf_cookies_with_playwright(account_name: str):
	"""使用 Playwright 获取 WAF cookies（隐私模式）"""
	print(f'[PROCESSING] {account_name}: Starting browser to get WAF cookies...')

	async with async_playwright() as p:
		import tempfile
		with tempfile.TemporaryDirectory() as temp_dir:
			context = await p.chromium.launch_persistent_context(
				user_data_dir=temp_dir,
				headless=False,
				user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				viewport={'width': 1920, 'height': 1080},
				args=[
					'--disable-blink-features=AutomationControlled',
					'--disable-dev-shm-usage',
					'--disable-web-security',
					'--disable-features=VizDisplayCompositor',
					'--no-sandbox',
				],
				)

			page = await context.new_page()

			try:
				print(f'[PROCESSING] {account_name}: Step 1: Access login page to get initial cookies...')

				await page.goto('https://anyrouter.top/login', wait_until='networkidle')

				try:
					await page.wait_for_function('document.readyState === "complete"', timeout=5000)
				except Exception:
					await page.wait_for_timeout(3000)

				cookies = await page.context.cookies()

				waf_cookies = {}
				for cookie in cookies:
					cookie_name = cookie.get('name')
					cookie_value = cookie.get('value')
					if cookie_name in ['acw_tc', 'cdn_sec_tc', 'acw_sc__v2'] and cookie_value is not None:
						waf_cookies[cookie_name] = cookie_value

				print(f'[INFO] {account_name}: Got {len(waf_cookies)} WAF cookies after step 1')

				required_cookies = ['acw_tc', 'cdn_sec_tc', 'acw_sc__v2']
				missing_cookies = [c for c in required_cookies if c not in waf_cookies]

				if missing_cookies:
					print(f'[FAILED] {account_name}: Missing WAF cookies: {missing_cookies}')
					await context.close()
					return None

				print(f'[SUCCESS] {account_name}: Successfully got all WAF cookies')

				await context.close()

				return waf_cookies

			except Exception as e:
				print(f'[FAILED] {account_name}: Error occurred while getting WAF cookies: {e}')
				await context.close()
				return None


def get_user_info(client, headers):
	"""获取用户信息"""
	try:
		response = client.get('https://anyrouter.top/api/user/self', headers=headers, timeout=30)

		if response.status_code == 200:
			data = response.json()
			if data.get('success'):
				user_data = data.get('data', {})
				quota = round(user_data.get('quota', 0) / 500000, 2)
				used_quota = round(user_data.get('used_quota', 0) / 500000, 2)
				return {
					'success': True,
					'quota': quota,
					'used_quota': used_quota,
					'display': f':money: Current balance: ${quota}, Used: ${used_quota}'
				}
		return {'success': False, 'error': f'Failed to get user info: HTTP {response.status_code}'}
	except Exception as e:
		return {'success': False, 'error': f'Failed to get user info: {str(e)[:50]}...'}


async def check_in_account(account_info, account_index):
	"""为单个账号执行签到操作"""
	account_name = get_account_display_name(account_info, account_index)
	print(f'\n[PROCESSING] Starting to process {account_name}')

	# 解析账号配置
	cookies_data = account_info.get('cookies', {})
	api_user = account_info.get('api_user', '')

	if not api_user:
		print(f'[FAILED] {account_name}: API user identifier not found')
		return False, None

	# 解析用户 cookies
	user_cookies = parse_cookies(cookies_data)
	if not user_cookies:
		print(f'[FAILED] {account_name}: Invalid configuration format')
		return False, None

	# 步骤1：获取 WAF cookies
	waf_cookies = await get_waf_cookies_with_playwright(account_name)
	if not waf_cookies:
		print(f'[FAILED] {account_name}: Unable to get WAF cookies')
		return False, None

	# 步骤2：使用 httpx 进行 API 请求
	client = httpx.Client(http2=True, timeout=30.0)

	try:
		# 合并 WAF cookies 和用户 cookies
		all_cookies = {**waf_cookies, **user_cookies}
		client.cookies.update(all_cookies)

		headers = {
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
			'Accept': 'application/json, text/plain, */*',
			'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
			'Accept-Encoding': 'gzip, deflate, br, zstd',
			'Referer': 'https://anyrouter.top/console',
			'Origin': 'https://anyrouter.top',
			'Connection': 'keep-alive',
			'Sec-Fetch-Dest': 'empty',
			'Sec-Fetch-Mode': 'cors',
			'Sec-Fetch-Site': 'same-origin',
			'new-api-user': api_user,
		}

		user_info = get_user_info(client, headers)
		if user_info and user_info.get('success'):
			print(user_info['display'])
		elif user_info:
			print(user_info.get('error', 'Unknown error'))

		print(f'[NETWORK] {account_name}: Executing check-in')

		# 更新签到请求头
		checkin_headers = headers.copy()
		checkin_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})

		response = client.post('https://anyrouter.top/api/user/sign_in', headers=checkin_headers, timeout=30)

		print(f'[RESPONSE] {account_name}: Response status code {response.status_code}')

		if response.status_code == 200:
			try:
				result = response.json()
				if result.get('ret') == 1 or result.get('code') == 0 or result.get('success'):
					print(f'[SUCCESS] {account_name}: Check-in successful!')
					return True, user_info
				else:
					error_msg = result.get('msg', result.get('message', 'Unknown error'))
					print(f'[FAILED] {account_name}: Check-in failed - {error_msg}')
					return False, user_info
			except json.JSONDecodeError:
				# 如果不是 JSON 响应，检查是否包含成功标识
				if 'success' in response.text.lower():
					print(f'[SUCCESS] {account_name}: Check-in successful!')
					return True, user_info
				else:
					print(f'[FAILED] {account_name}: Check-in failed - Invalid response format')
					return False, user_info
		else:
			print(f'[FAILED] {account_name}: Check-in failed - HTTP {response.status_code}')
			return False, user_info

	except Exception as e:
		print(f'[FAILED] {account_name}: Error occurred during check-in process - {str(e)[:50]}...')
		return False, None
	finally:
		client.close()


async def main():
	"""主函数"""
	print('[SYSTEM] AnyRouter.top multi-account auto check-in script started (using Playwright)')
	print(f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

	# 加载账号配置
	accounts = load_accounts()
	if not accounts:
		print('[FAILED] Unable to load account configuration, program exits')
		sys.exit(1)

	print(f'[INFO] Found {len(accounts)} account configurations')

	# 加载余额hash
	last_balance_hash = load_balance_hash()

	# 为每个账号执行签到
	success_count = 0
	total_count = len(accounts)
	account_results: List[AccountResult] = []  # 使用结构化数据存储结果
	current_balances = {}
	need_notify = False  # 是否需要发送通知
	balance_changed = False  # 余额是否有变化

	for i, account in enumerate(accounts):
		account_key = f'account_{i + 1}'
		try:
			success, user_info = await check_in_account(account, i)
			account_name = get_account_display_name(account, i)

			# 创建账号结果
			account_result = AccountResult(
				name=account_name,
				status="success" if success else "failed"
			)

			if success:
				success_count += 1

			# 检查是否需要通知
			should_notify_this_account = False

			# 如果签到失败，需要通知
			if not success:
				should_notify_this_account = True
				need_notify = True
				print(f'[NOTIFY] {account_name} failed, will send notification')

			# 收集余额数据和处理结果
			if user_info and user_info.get('success'):
				current_quota = user_info['quota']
				current_used = user_info['used_quota']
				current_balances[account_key] = {'quota': current_quota, 'used': current_used}

				# 设置账号结果的余额信息
				account_result.quota = current_quota
				account_result.used = current_used
			elif user_info:
				# 设置错误信息
				account_result.error = user_info.get('error', '未知错误')

			# 只有需要通知的账号才添加到结果列表
			if should_notify_this_account:
				account_results.append(account_result)

		except Exception as e:
			account_name = get_account_display_name(account, i)
			print(f'[FAILED] {account_name} processing exception: {e}')
			need_notify = True  # 异常也需要通知

			# 创建失败的账号结果
			account_result = AccountResult(
				name=account_name,
				status="failed",
				error=f'异常: {str(e)[:50]}...'
			)
			account_results.append(account_result)

	# 检查余额变化
	current_balance_hash = generate_balance_hash(current_balances) if current_balances else None
	if current_balance_hash:
		if last_balance_hash is None:
			# 首次运行
			balance_changed = True
			need_notify = True
			print('[NOTIFY] First run detected, will send notification with current balances')
		elif current_balance_hash != last_balance_hash:
			# 余额有变化
			balance_changed = True
			need_notify = True
			print('[NOTIFY] Balance changes detected, will send notification')
		else:
			print('[INFO] No balance changes detected')

	# 为有余额变化的情况添加所有成功账号到通知内容
	if balance_changed:
		for i, account in enumerate(accounts):
			account_key = f'account_{i + 1}'
			if account_key in current_balances:
				account_name = get_account_display_name(account, i)
				# 检查是否已经在结果列表中（避免重复）
				if not any(result.name == account_name for result in account_results):
					account_result = AccountResult(
						name=account_name,
						status="success",
						quota=current_balances[account_key]["quota"],
						used=current_balances[account_key]["used"]
					)
					account_results.append(account_result)

	# 保存当前余额hash
	if current_balance_hash:
		save_balance_hash(current_balance_hash)

	if need_notify and account_results:
		# 构建结构化通知数据
		stats = NotificationStats(
			success_count=success_count,
			failed_count=total_count - success_count,
			total_count=total_count
		)

		notification_data = NotificationData(
			accounts=account_results,
			stats=stats,
			timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		)

		# 发送通知
		notify.push_message('AnyRouter 签到提醒', notification_data, msg_type='text')
		print('[NOTIFY] Notification sent due to failures or balance changes')
	else:
		print('[INFO] All accounts successful and no balance changes detected, notification skipped')

	# 日志总结
	print(f'[RESULT] Final result: Success {success_count}/{total_count}, Failed {total_count - success_count}/{total_count}')

	# 设置退出码
	sys.exit(0 if success_count > 0 else 1)


def run_main():
	"""运行主函数的包装函数"""
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print('\n[WARNING] Program interrupted by user')
		sys.exit(1)
	except Exception as e:
		print(f'\n[FAILED] Error occurred during program execution: {e}')
		sys.exit(1)


if __name__ == '__main__':
	run_main()
