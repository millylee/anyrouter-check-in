"""代理配置：读取环境变量并供浏览器 / HTTP 客户端使用。"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit


def get_proxy_server(*, use_proxy: bool = True) -> str | None:
	"""按平台配置读取 CHECKIN_PROXY_URL；use_proxy=False 时不返回代理地址。"""
	if not use_proxy:
		return None
	server = os.getenv('CHECKIN_PROXY_URL', '').strip()
	return server or None


def get_playwright_proxy(*, use_proxy: bool = True) -> dict[str, str] | None:
	server = get_proxy_server(use_proxy=use_proxy)
	if not server:
		return None
	parsed = urlsplit(server)
	if not parsed.username:
		return {'server': server}
	host = parsed.hostname or ''
	if ':' in host and not host.startswith('['):
		host = f'[{host}]'
	if parsed.port:
		host = f'{host}:{parsed.port}'
	return {
		'server': urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment)),
		'username': parsed.username,
		'password': parsed.password or '',
	}
