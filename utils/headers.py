"""浏览器请求头工具模块"""

from __future__ import annotations

from typing import Mapping

DEFAULT_USER_AGENT = (
	'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
	'(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
)

DEFAULT_SEC_CH_UA = (
	'"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"'
)


def get_browser_headers(
	domain: str | None = None,
	extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
	"""生成标准的现代桌面 Chrome 浏览器标头集。"""
	headers: dict[str, str] = {
		'User-Agent': DEFAULT_USER_AGENT,
		'Accept': 'application/json, text/plain, */*',
		'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
		'Accept-Encoding': 'gzip, deflate, br, zstd',
		'sec-ch-ua': DEFAULT_SEC_CH_UA,
		'sec-ch-ua-mobile': '?0',
		'sec-ch-ua-platform': '"Windows"',
		'Sec-Fetch-Dest': 'empty',
		'Sec-Fetch-Mode': 'cors',
		'Sec-Fetch-Site': 'same-origin',
		'Connection': 'keep-alive',
	}

	if domain:
		clean_domain = domain.rstrip('/')
		headers['Origin'] = clean_domain
		headers['Referer'] = f'{clean_domain}/'

	if extra:
		headers.update(extra)

	return headers
