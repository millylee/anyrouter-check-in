#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
anyrouter.top 批量登录并导出 cookies + api_user 的脚本
输出文件: anyrouter_accounts.json (格式化的 JSON 文件)

使用方法:
1) 在 user.json 中配置用户信息，格式如下:
   [
     {
       "name": "账号名称",
       "provider": "anyrouter.top",
       "username": "用户名",
       "password": "密码"
     }
   ]
2) 运行: python3 auto_login.py
3) 输出格式: 格式化的 JSON 文件
4) 合并为单行: python3 merge_accounts.py
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# -------- 配置区 --------
BASE_URL = "https://anyrouter.top"
# 获取脚本所在目录，确保相对路径正确
SCRIPT_DIR = Path(__file__).parent
USER_JSON_FILE = SCRIPT_DIR / "user.json"  # 用户信息文件
OUT_FILENAME = SCRIPT_DIR / "anyrouter_accounts.json"  # 输出 JSON 文件
HEADLESS = True  # 是否无头模式运行浏览器
# ------------------------

def login_and_extract(page, username: str, password: str):
    """使用 Playwright 登录并提取 session cookie 和 api_user"""
    try:
        # 访问登录页面
        print(f"  访问登录页面...")
        page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30000)

        # 关闭可能出现的公告对话框
        try:
            print(f"  检查并关闭公告对话框...")
            # 等待公告对话框出现（如果有的话）
            close_button = page.locator('button:has-text("今日关闭"), button:has-text("关闭公告"), .semi-modal-close')
            if close_button.count() > 0:
                close_button.first.click(timeout=2000)
                print(f"  已关闭公告对话框")
                time.sleep(1)
        except Exception as e:
            print(f"  无公告对话框或已关闭: {e}")

        # 等待登录表单加载
        page.wait_for_selector('input[name="username"]', timeout=10000)

        # 填写用户名和密码
        print(f"  填写登录信息...")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)

        # 点击登录按钮
        print(f"  点击登录按钮...")
        page.click('button[type="submit"]:has-text("继续")')

        # 等待登录完成 - 等待页面跳转或者错误信息
        print(f"  等待登录响应...")
        time.sleep(3)  # 给服务器一些响应时间

        # 检查是否登录成功 - 通常登录成功后会跳转到首页或个人中心
        current_url = page.url
        print(f"  当前 URL: {current_url}")

        # 获取所有 cookies
        cookies = page.context.cookies()
        session_cookie = None
        for cookie in cookies:
            if cookie['name'] == 'session':
                session_cookie = cookie['value']
                break

        print(f"  Session Cookie: {session_cookie[:20] if session_cookie else 'None'}...")

        # 尝试获取用户信息 - 访问 API 或从页面中提取
        api_user = None

        # 方法1: 尝试调用用户信息 API
        try:
            response = page.goto(f"{BASE_URL}/api/user/info", wait_until="networkidle", timeout=10000)
            if response and response.status == 200:
                user_data = response.json()
                print(f"  用户信息 API 响应: {json.dumps(user_data, ensure_ascii=False)}")
                if isinstance(user_data, dict):
                    data = user_data.get('data', {})
                    api_user = data.get('id') or data.get('user_id')
        except Exception as e:
            print(f"  获取用户信息失败: {e}")

        # 方法2: 从 localStorage 中获取
        if not api_user:
            try:
                local_storage = page.evaluate("() => { return JSON.stringify(localStorage); }")
                print(f"  LocalStorage: {local_storage}")
                storage_data = json.loads(local_storage)
                for key, value in storage_data.items():
                    try:
                        data = json.loads(value)
                        if isinstance(data, dict) and 'id' in data:
                            api_user = data['id']
                            break
                    except:
                        continue
            except Exception as e:
                print(f"  读取 localStorage 失败: {e}")

        print(f"  API User: {api_user}")

        return {
            "success": bool(session_cookie or api_user),
            "session_cookie": session_cookie,
            "api_user": str(api_user) if api_user else None,
            "current_url": current_url,
            "all_cookies": {c['name']: c['value'] for c in cookies}
        }

    except Exception as e:
        print(f"  错误: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_cookie": None,
            "api_user": None
        }

def main():
    results = []

    # 读取用户信息文件
    try:
        with open(USER_JSON_FILE, "r", encoding="utf-8") as f:
            user_list = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到用户信息文件 {USER_JSON_FILE}")
        return
    except json.JSONDecodeError as e:
        print(f"错误: 无法解析 {USER_JSON_FILE}，JSON 格式错误: {e}")
        return

    if not user_list:
        print(f"{USER_JSON_FILE} 中没有用户信息")
        return

    with sync_playwright() as p:
        # 启动浏览器
        print("启动浏览器...")
        browser = p.chromium.launch(headless=HEADLESS)

        for idx, user in enumerate(user_list):
            # 从 JSON 中读取字段
            name = user.get("name", "").strip()
            provider = user.get("provider", "").strip()
            username = user.get("username", "").strip()
            password = user.get("password", "").strip()

            # 设置默认值
            if not provider:
                provider = "anyrouter.top"
            if not name:
                name = f"账号{idx+1}"

            if not username or not password:
                print(f"[跳过] 第 {idx+1} 个条目缺少 username 或 password")
                continue

            print(f"\n[{idx+1}] 登录 {provider} -> {username} ...")

            # 为每个账号创建新的浏览器上下文（隔离 cookies）
            context = browser.new_context()
            page = context.new_page()

            try:
                # 进行登录
                out_item = {
                    "name": name,
                    "provider": provider,
                    "api_user": info.get("api_user") or "",
                    "cookies": {
                        "session": info.get("session_cookie") or ""
                    }
                }
                info = login_and_extract(page, username, password)

                # 组装输出格式 - 简化为只包含必要信息

                results.append(out_item)

            finally:
                # 关闭上下文
                context.close()

            # 小睡一下，避免短时间内对方封禁
            if idx < len(user_list) - 1:
                print(f"  等待 2 秒...")
                time.sleep(2)

        # 关闭浏览器
        browser.close()

    # 写入格式化的 JSON 文件
    with open(OUT_FILENAME, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n已完成，输出到: {OUT_FILENAME}")
    print(f"共处理 {len(results)} 个账号")
    print("\n提示: 使用 'python merge_accounts.py' 将 JSON 转换为单行格式")

if __name__ == "__main__":
    main()