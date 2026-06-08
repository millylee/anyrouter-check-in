"""调试模式开关：控制敏感日志与调试产物（截图等）。"""

from __future__ import annotations

import os


def is_debug_enabled() -> bool:
	"""是否开启调试模式，读取 DEBUG_MODE，默认 false。"""
	raw = os.getenv('DEBUG_MODE', '').strip().lower()
	return raw in {'1', 'true', 'yes', 'on'}


def debug_print(message: str) -> None:
	"""仅在调试模式下输出日志。"""
	if is_debug_enabled():
		print(message)
