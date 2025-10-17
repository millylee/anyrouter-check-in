#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将 anyrouter_accounts.json 转换为单行格式输出到 anyrouter_accounts.txt

使用方法:
1) 确保 anyrouter_accounts.json 文件存在
2) 运行: python3 merge_accounts.py
3) 输出文件: anyrouter_accounts.txt (单行 JSON，可直接用于 .env 文件)
"""

import json
from pathlib import Path

# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent
INPUT_FILE = SCRIPT_DIR / "anyrouter_accounts.json"
OUTPUT_FILE = SCRIPT_DIR / "anyrouter_accounts.txt"


def merge_accounts():
    """将 JSON 文件转换为单行格式"""
    try:
        # 读取 JSON 文件
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)

        # 转换为单行 JSON（紧凑格式，无空格）
        output_line = json.dumps(accounts, ensure_ascii=False, separators=(',', ':'))

        # 写入输出文件
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(output_line)

        print(f"✓ 成功转换 {len(accounts)} 个账号")
        print(f"✓ 输入文件: {INPUT_FILE}")
        print(f"✓ 输出文件: {OUTPUT_FILE}")
        print(f"\n输出内容预览:")
        print(f"{output_line[:200]}..." if len(output_line) > 200 else output_line)

    except FileNotFoundError:
        print(f"✗ 错误: 找不到文件 {INPUT_FILE}")
        print(f"  请先运行 'python auto_login.py' 生成账号数据")
    except json.JSONDecodeError as e:
        print(f"✗ 错误: JSON 格式错误: {e}")
    except Exception as e:
        print(f"✗ 错误: {e}")


if __name__ == "__main__":
    merge_accounts()
