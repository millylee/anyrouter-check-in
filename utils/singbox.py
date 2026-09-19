#!/usr/bin/env python3
"""把 Xray 分享链接转换成 sing-box 配置。

支持的分享链接（按行分隔，可以是一个或多个）：

- `vless://`              VLESS
- `vmess://`              VMess
- `trojan://`             Trojan
- `ss://`                 Shadowsocks
- `hy2://` / `hysteria2://`  Hysteria2

所有节点会被放进一个 `urltest` 出站组，由 sing-box 自动测速选节点，
本地通过 `mixed` 入站（HTTP/SOCKS 同一个端口）暴露给签到脚本。

命令行用法（由 `scripts/setup_singbox_proxy.sh` 调用）：

    python3 -m utils.singbox --links-file links.txt --port 7890 -o config.json

分享链接按优先级从 `--links`、`--links-file`、环境变量 `PROXY_SHARE_LINKS` 读取。
"""

from __future__ import annotations

import argparse
import base64
import binascii
import ipaddress
import json
import os
import sys
from typing import Any, Callable
from urllib.parse import parse_qsl, unquote, urlsplit

SUPPORTED_SCHEMES: tuple[str, ...] = (
	'vless',
	'vmess',
	'trojan',
	'ss',
	'hy2',
	'hysteria2',
	'socks',
	'socks4',
	'socks4a',
	'socks5',
	'http',
	'https',
)
DEFAULT_TEST_URL = 'https://www.google.com/generate_204'
DEFAULT_GROUP_TAG = 'CHECKIN'

_UTLS_FINGERPRINTS = frozenset(
	{'chrome', 'firefox', 'safari', 'ios', 'android', 'edge', '360', '360se7', '360ee7', 'qq', 'random', 'randomized'}
)
_VMESS_SECURITY = frozenset({'auto', 'none', 'aes-128-gcm', 'chacha20-poly1305', 'packetaddr'})
_PACKET_ENCODING = frozenset({'packetaddr', 'xudp'})
_TLS_SECURITY = frozenset({'tls', 'reality'})
_SOCKS_VERSIONS = {'socks': '5', 'socks5': '5', 'socks4': '4', 'socks4a': '4a'}

ParsedNode = tuple[str, dict[str, Any]]


def _warn(message: str) -> None:
	"""告警统一走 stderr，避免污染 stdout 上的 JSON。"""
	print(f'[WARN] {message}', file=sys.stderr)


def _info(message: str) -> None:
	print(f'[INFO] {message}', file=sys.stderr)


def mask_link(link: str) -> str:
	"""日志脱敏：分享链接里带着密码/UUID，只保留协议与服务器地址。"""
	scheme, sep, rest = link.strip().partition('://')
	if not sep:
		return '<不是合法的分享链接>'
	prefix = f'{scheme}://'
	if '@' in rest:
		_, _, rest = rest.rpartition('@')
		prefix += '***@'
	server = rest.split('?', 1)[0].split('#', 1)[0]
	return f'{prefix}{server}'


def _b64decode(value: str) -> bytes | None:
	"""解码 base64 / base64url，自动补齐 padding；失败或解出空内容都返回 None。"""
	text = value.strip().replace(' ', '+').replace('-', '+').replace('_', '/')
	if not text:
		return None
	text += '=' * (-len(text) % 4)
	try:
		decoded = base64.b64decode(text.encode('ascii'), validate=True)
	except (binascii.Error, UnicodeDecodeError, ValueError):
		return None
	return decoded or None


def _query_dict(query: str) -> dict[str, str]:
	"""解析查询串；重复的键保留最后一个。"""
	return {key: value for key, value in parse_qsl(query, keep_blank_values=True)}


def _split_netloc(netloc: str) -> tuple[str, str, str]:
	"""拆分 netloc，返回 (已解码的 userinfo, host, port 文本)。"""
	userinfo, _, rest = netloc.rpartition('@')
	if rest.startswith('['):
		host, _, tail = rest[1:].partition(']')
		port_text = tail[1:] if tail.startswith(':') else ''
	else:
		host, _, port_text = rest.partition(':')
	return unquote(userinfo), host.strip(), port_text.strip()


def _to_int(value: Any) -> int:
	if isinstance(value, bool):
		return 0
	if isinstance(value, int):
		return value
	text = str(value).strip()
	return int(text) if text.isdigit() else 0


def _to_port(value: Any) -> int | None:
	port = _to_int(value)
	return port if 0 < port < 65536 else None


def _truthy(value: str) -> bool:
	return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _is_ip(value: str) -> bool:
	try:
		ipaddress.ip_address(value)
	except ValueError:
		return False
	return True


def _fingerprint(value: str) -> str:
	"""归一化 uTLS 指纹；sing-box 不认识的指纹直接丢弃，避免配置校验失败。"""
	fingerprint = value.strip().lower()
	if fingerprint and fingerprint not in _UTLS_FINGERPRINTS:
		_warn(f'忽略不支持的 uTLS 指纹: {value}')
		return ''
	return fingerprint


def _alpn(value: str) -> list[str]:
	return [item.strip() for item in value.split(',') if item.strip()]


def _tls(
	*,
	server_name: str = '',
	insecure: bool = False,
	alpn: str = '',
	fingerprint: str = '',
	reality_key: str = '',
	reality_short_id: str = '',
) -> dict[str, Any]:
	"""构造 sing-box 的 tls 字段。

	`server_name` 留空时 sing-box 会用服务器地址兜底，所以不必强行猜测 SNI。
	"""
	tls: dict[str, Any] = {'enabled': True}
	if server_name:
		tls['server_name'] = server_name
	if insecure:
		tls['insecure'] = True
	alpn_list = _alpn(alpn)
	if alpn_list:
		tls['alpn'] = alpn_list
	if fingerprint:
		tls['utls'] = {'enabled': True, 'fingerprint': fingerprint}
	if reality_key:
		reality: dict[str, Any] = {'enabled': True, 'public_key': reality_key}
		if reality_short_id:
			reality['short_id'] = reality_short_id
		tls['reality'] = reality
		tls.setdefault('utls', {'enabled': True, 'fingerprint': 'chrome'})
	return tls


def _transport(net: str, params: dict[str, str]) -> dict[str, Any] | None:
	"""把 v2ray 的传输方式转换成 sing-box transport；tcp/raw 不需要 transport。"""
	kind = net.strip().lower()
	if kind in {'', 'tcp', 'raw', 'none'}:
		return None
	if kind in {'ws', 'websocket'}:
		transport: dict[str, Any] = {'type': 'ws'}
		if params.get('path'):
			transport['path'] = params['path']
		if params.get('host'):
			transport['headers'] = {'Host': params['host']}
		early_data = params.get('ed') or params.get('maxEarlyData') or ''
		if early_data.isdigit() and int(early_data) > 0:
			transport['max_early_data'] = int(early_data)
			transport['early_data_header_name'] = params.get('eh') or 'Sec-WebSocket-Protocol'
		return transport
	if kind in {'grpc', 'gun'}:
		transport = {'type': 'grpc'}
		service_name = params.get('serviceName') or params.get('path', '').strip('/')
		if service_name:
			transport['service_name'] = service_name
		return transport
	if kind in {'h2', 'http'}:
		transport = {'type': 'http', 'method': 'PUT'}
		if params.get('path'):
			transport['path'] = params['path']
		if params.get('host'):
			transport['headers'] = {'Host': params['host']}
		return transport
	if kind == 'httpupgrade':
		transport = {'type': 'httpupgrade'}
		if params.get('path'):
			transport['path'] = params['path']
		if params.get('host'):
			transport['host'] = params['host']
		return transport
	if kind == 'quic':
		return {'type': 'quic'}
	_warn(f'忽略不支持的传输方式: {net}')
	return None


def _sni(params: dict[str, str]) -> str:
	"""SNI 优先取 sni，其次取 host（host 是 IP 时不能当 SNI 用）。"""
	server_name = params.get('sni', '').strip()
	if server_name:
		return server_name
	host = params.get('host', '').strip()
	return '' if not host or _is_ip(host) else host


def _parse_vless(link: str) -> ParsedNode | None:
	split = urlsplit(link)
	userinfo, host, port_text = _split_netloc(split.netloc)
	port = _to_port(port_text)
	if not userinfo or not host or port is None:
		_warn(f'VLESS 链接缺少 uuid / 地址 / 端口，已跳过: {mask_link(link)}')
		return None
	params = _query_dict(split.query)
	outbound: dict[str, Any] = {'type': 'vless', 'server': host, 'server_port': port, 'uuid': userinfo}

	flow = params.get('flow', '').strip()
	if flow:
		if flow == 'xtls-rprx-vision':
			outbound['flow'] = flow
		else:
			_warn(f'忽略不支持的 flow: {flow}')

	packet_encoding = params.get('packetEncoding', '').strip().lower()
	if packet_encoding in _PACKET_ENCODING:
		outbound['packet_encoding'] = packet_encoding

	security = params.get('security', '').strip().lower()
	if not security:
		# 链接没写 security 时按 TLS 相关参数推断，避免给明文节点强行套上 TLS
		security = 'reality' if params.get('pbk') else ('tls' if (params.get('sni') or params.get('fp')) else 'none')
	insecure = _truthy(params.get('allowInsecure', '')) or _truthy(params.get('insecure', ''))
	if security in _TLS_SECURITY:
		is_reality = security == 'reality'
		outbound['tls'] = _tls(
			server_name=_sni(params),
			insecure=insecure,
			alpn=params.get('alpn', ''),
			fingerprint=_fingerprint(params.get('fp', '')),
			reality_key=params.get('pbk', '') if is_reality else '',
			reality_short_id=params.get('sid', '') if is_reality else '',
		)
	elif security != 'none':
		_warn(f'忽略不支持的 security: {security}')

	transport = _transport(params.get('type') or params.get('network') or '', params)
	if transport:
		outbound['transport'] = transport
	return unquote(split.fragment), outbound


def _parse_vmess(link: str) -> ParsedNode | None:
	rest = link.split('://', 1)[1]
	payload, _, fragment = rest.partition('#')
	raw = _b64decode(payload)
	if raw is None:
		_warn(f'VMess 链接 base64 解码失败，已跳过: {mask_link(link)}')
		return None
	try:
		data = json.loads(raw.decode('utf-8'))
	except (UnicodeDecodeError, json.JSONDecodeError):
		_warn(f'VMess 链接不是合法的 JSON，已跳过: {mask_link(link)}')
		return None
	if not isinstance(data, dict):
		_warn(f'VMess 链接内容不是对象，已跳过: {mask_link(link)}')
		return None

	host = str(data.get('add', '')).strip()
	port = _to_port(data.get('port', ''))
	uuid = str(data.get('id', '')).strip()
	if not host or port is None or not uuid:
		_warn(f'VMess 链接缺少地址 / 端口 / uuid，已跳过: {mask_link(link)}')
		return None
	outbound: dict[str, Any] = {'type': 'vmess', 'server': host, 'server_port': port, 'uuid': uuid}

	security = str(data.get('scy', '')).strip().lower() or 'auto'
	if security == 'zero':
		security = 'none'
	if security in _VMESS_SECURITY:
		outbound['security'] = security
	else:
		_warn(f'忽略不支持的 VMess 加密方式: {security}')

	alter_id = _to_int(data.get('aid', 0))
	if alter_id > 0:
		outbound['alter_id'] = alter_id

	net = str(data.get('net', '')).strip().lower()
	header_type = str(data.get('type', '')).strip().lower()
	params = {
		'host': str(data.get('host', '') or '').strip(),
		'path': str(data.get('path', '') or '').strip(),
		'serviceName': str(data.get('serviceName', '') or '').strip(),
	}
	if net in {'', 'tcp', 'raw'} and header_type == 'http':
		net = 'h2'
	transport = _transport(net, params)
	if transport:
		outbound['transport'] = transport

	tls_value = str(data.get('tls', '')).strip().lower()
	if tls_value in _TLS_SECURITY:
		outbound['tls'] = _tls(
			server_name=str(data.get('sni', '') or '').strip() or _sni(params),
			insecure=_truthy(str(data.get('allowInsecure', '') or '')),
			alpn=str(data.get('alpn', '') or ''),
			fingerprint=_fingerprint(str(data.get('fp', '') or '')),
			reality_key=str(data.get('pbk', '') or '') if tls_value == 'reality' else '',
			reality_short_id=str(data.get('sid', '') or '') if tls_value == 'reality' else '',
		)
	return unquote(fragment), outbound


def _parse_trojan(link: str) -> ParsedNode | None:
	split = urlsplit(link)
	userinfo, host, port_text = _split_netloc(split.netloc)
	port = _to_port(port_text)
	if not userinfo or not host or port is None:
		_warn(f'Trojan 链接缺少密码 / 地址 / 端口，已跳过: {mask_link(link)}')
		return None
	params = _query_dict(split.query)
	outbound: dict[str, Any] = {'type': 'trojan', 'server': host, 'server_port': port, 'password': userinfo}

	transport = _transport(params.get('type') or params.get('network') or '', params)
	if transport:
		outbound['transport'] = transport

	# Trojan 必须走 TLS，所以这里无条件生成 tls 字段
	outbound['tls'] = _tls(
		server_name=_sni(params),
		insecure=_truthy(params.get('allowInsecure', '')) or _truthy(params.get('insecure', '')),
		alpn=params.get('alpn', ''),
		fingerprint=_fingerprint(params.get('fp', '')),
		reality_key=params.get('pbk', ''),
		reality_short_id=params.get('sid', ''),
	)
	return unquote(split.fragment), outbound


def _split_ss_userinfo(userinfo: str) -> tuple[str, str | None]:
	"""还原 `method:password`。

	SIP002 链接里 userinfo 是 `base64(method:password)`；`:` 不属于 base64 字符集，
	所以带 `:` 的就是明文形式，否则按 base64 解。
	"""
	if ':' in userinfo:
		method, _, password = userinfo.partition(':')
		return method.strip(), password
	raw = _b64decode(userinfo)
	if raw is None:
		return '', None
	try:
		decoded = raw.decode('utf-8')
	except UnicodeDecodeError:
		return '', None
	if ':' not in decoded:
		return '', None
	method, _, password = decoded.partition(':')
	return method.strip(), password


def _parse_shadowsocks(link: str) -> ParsedNode | None:
	split = urlsplit(link)
	params = _query_dict(split.query)
	if params.get('plugin'):
		# 插件需要额外的二进制（obfs-local / v2ray-plugin），runner 上没有，硬塞进配置会让整个 sing-box 起不来
		_warn(f'Shadowsocks 插件节点暂不支持，已跳过: {mask_link(link)}')
		return None
	userinfo, host, port_text = _split_netloc(split.netloc)
	port = _to_port(port_text)
	if not host or port is None:
		_warn(f'Shadowsocks 链接缺少地址 / 端口，已跳过: {mask_link(link)}')
		return None
	method, password = _split_ss_userinfo(userinfo)
	if not method or password is None:
		_warn(f'Shadowsocks 链接无法解析加密方式，已跳过: {mask_link(link)}')
		return None
	outbound: dict[str, Any] = {
		'type': 'shadowsocks',
		'server': host,
		'server_port': port,
		'method': method,
		'password': password,
	}
	return unquote(split.fragment), outbound


def _parse_hysteria2(link: str) -> ParsedNode | None:
	split = urlsplit(link)
	userinfo, host, port_text = _split_netloc(split.netloc)
	port = _to_port(port_text)
	if not userinfo or not host or port is None:
		_warn(f'Hysteria2 链接缺少密码 / 地址 / 端口，已跳过: {mask_link(link)}')
		return None
	params = _query_dict(split.query)
	# hy2 的认证串本身可以是 user:password，整体作为 password 传给 sing-box
	outbound: dict[str, Any] = {'type': 'hysteria2', 'server': host, 'server_port': port, 'password': userinfo}

	up_mbps = _to_int(params.get('upmbps') or params.get('up') or '')
	down_mbps = _to_int(params.get('downmbps') or params.get('down') or '')
	if up_mbps > 0:
		outbound['up_mbps'] = up_mbps
	if down_mbps > 0:
		outbound['down_mbps'] = down_mbps

	obfs = params.get('obfs', '').strip().lower()
	if obfs and obfs != 'none':
		if obfs != 'salamander':
			_warn(f'忽略不支持的 Hysteria2 混淆: {obfs}')
		elif params.get('obfs-password'):
			outbound['obfs'] = {'type': 'salamander', 'password': params['obfs-password']}

	outbound['tls'] = _tls(
		server_name=params.get('sni', '').strip() or ('' if _is_ip(host) else host),
		insecure=_truthy(params.get('insecure', '')) or _truthy(params.get('allowInsecure', '')),
		alpn=params.get('alpn', ''),
	)
	return unquote(split.fragment), outbound


def _split_credentials(userinfo: str) -> tuple[str, str]:
	"""拆分 `user:pass`；没有冒号时整体当用户名（SOCKS/HTTP 代理允许只填用户名或都不填）。"""
	if not userinfo:
		return '', ''
	username, sep, password = userinfo.partition(':')
	if not sep:
		return username, ''
	return username, password


def _parse_socks(link: str) -> ParsedNode | None:
	"""socks:// socks4:// socks4a:// socks5://user:pass@host:port#备注"""
	split = urlsplit(link)
	userinfo, host, port_text = _split_netloc(split.netloc)
	port = _to_port(port_text)
	if not host or port is None:
		_warn(f'SOCKS 链接缺少地址 / 端口，已跳过: {mask_link(link)}')
		return None
	outbound: dict[str, Any] = {
		'type': 'socks',
		'server': host,
		'server_port': port,
		'version': _SOCKS_VERSIONS.get(split.scheme.strip().lower(), '5'),
	}
	username, password = _split_credentials(userinfo)
	if username:
		outbound['username'] = username
	if password:
		outbound['password'] = password
	return unquote(split.fragment), outbound


def _parse_http(link: str) -> ParsedNode | None:
	"""http:// https://user:pass@host:port#备注 —— 生成 sing-box 的 HTTP CONNECT 出站。

	端口缺省时按 URL 语义补 80 / 443；`https://` 额外打开 tls。
	"""
	split = urlsplit(link)
	scheme = split.scheme.strip().lower()
	tls_enabled = scheme == 'https'
	params = _query_dict(split.query)
	userinfo, host, port_text = _split_netloc(split.netloc)
	if not host:
		_warn(f'HTTP 代理链接缺少地址，已跳过: {mask_link(link)}')
		return None
	if port_text:
		port = _to_port(port_text)
		if port is None:
			_warn(f'HTTP 代理链接端口非法，已跳过: {mask_link(link)}')
			return None
	else:
		port = 443 if tls_enabled else 80
	outbound: dict[str, Any] = {'type': 'http', 'server': host, 'server_port': port}
	username, password = _split_credentials(userinfo)
	if username:
		outbound['username'] = username
	if password:
		outbound['password'] = password
	if tls_enabled:
		outbound['tls'] = _tls(
			server_name=params.get('sni', '').strip() or ('' if _is_ip(host) else host),
			insecure=_truthy(params.get('insecure', '')) or _truthy(params.get('allowInsecure', '')),
		)
	return unquote(split.fragment), outbound


_PARSERS: dict[str, Callable[[str], ParsedNode | None]] = {
	'vless': _parse_vless,
	'vmess': _parse_vmess,
	'trojan': _parse_trojan,
	'ss': _parse_shadowsocks,
	'hy2': _parse_hysteria2,
	'hysteria2': _parse_hysteria2,
	'socks': _parse_socks,
	'socks4': _parse_socks,
	'socks4a': _parse_socks,
	'socks5': _parse_socks,
	'http': _parse_http,
	'https': _parse_http,
}


def parse_share_link(link: str) -> ParsedNode | None:
	"""解析单条分享链接，返回 (备注, 出站配置)；不支持或残缺时返回 None。"""
	text = link.strip()
	scheme, sep, _ = text.partition('://')
	if not sep:
		return None
	parser = _PARSERS.get(scheme.strip().lower())
	if parser is None:
		_warn(f'不支持的协议 {scheme.strip()}（支持: {", ".join(SUPPORTED_SCHEMES)}）: {mask_link(text)}')
		return None
	return parser(text)


def _unique_tag(base: str, used: set[str]) -> str:
	"""备注当 tag，压掉空白与换行并去重。"""
	tag = ' '.join(str(base).split())[:60].strip() or 'node'
	candidate = tag
	suffix = 2
	while candidate in used:
		candidate = f'{tag} #{suffix}'
		suffix += 1
	used.add(candidate)
	return candidate


def parse_share_links(raw: str) -> list[ParsedNode]:
	"""按行解析分享链接，返回 [(tag, 出站配置)]。

	空行与 `#` 开头的行会被忽略；解析失败的行只告警并跳过，不影响其它节点。
	"""
	nodes: list[ParsedNode] = []
	used: set[str] = set()
	for lineno, line in enumerate(raw.splitlines(), start=1):
		link = line.strip()
		if not link or link.startswith('#'):
			continue
		parsed = parse_share_link(link)
		if parsed is None:
			_warn(f'第 {lineno} 行无法解析，已跳过: {mask_link(link)}')
			continue
		remark, outbound = parsed
		nodes.append((_unique_tag(remark or outbound['server'], used), outbound))
	return nodes


def build_config(
	nodes: list[ParsedNode],
	*,
	listen: str = '127.0.0.1',
	port: int = 7890,
	test_url: str = DEFAULT_TEST_URL,
	group_tag: str = DEFAULT_GROUP_TAG,
	interval: str = '3m',
	tolerance: int = 150,
) -> dict[str, Any]:
	"""把解析好的节点组装成完整的 sing-box 配置。"""
	if not nodes:
		raise ValueError('没有解析出任何可用的代理节点')

	outbounds: list[dict[str, Any]] = []
	for tag, outbound in nodes:
		kind = outbound['type']
		rest = {key: value for key, value in outbound.items() if key != 'type'}
		outbounds.append({'type': kind, 'tag': tag, **rest})

	outbounds.append(
		{
			'type': 'urltest',
			'tag': group_tag,
			'outbounds': [tag for tag, _ in nodes],
			'url': test_url,
			'interval': interval,
			'tolerance': tolerance,
		}
	)

	return {
		'log': {'level': 'warn', 'timestamp': True},
		'inbounds': [{'type': 'mixed', 'tag': 'mixed-in', 'listen': listen, 'listen_port': port}],
		'outbounds': outbounds,
		'route': {'final': group_tag},
	}


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
	cli = argparse.ArgumentParser(description='把 Xray 分享链接转换成 sing-box 配置')
	cli.add_argument('--links', help='分享链接，多个用换行分隔')
	cli.add_argument('--links-file', help='包含分享链接的文件，每行一个')
	cli.add_argument('-o', '--output', help='输出 JSON 路径，默认写到标准输出')
	cli.add_argument('--listen', default='127.0.0.1', help='监听地址，默认 127.0.0.1')
	cli.add_argument('--port', type=int, default=7890, help='mixed 端口，默认 7890')
	cli.add_argument('--test-url', default=DEFAULT_TEST_URL, help='urltest 探测地址')
	cli.add_argument('--group-tag', default=DEFAULT_GROUP_TAG, help='出站组 tag，默认 CHECKIN')
	args = cli.parse_args(argv)

	raw = args.links or ''
	if not raw and args.links_file:
		with open(args.links_file, encoding='utf-8') as handle:
			raw = handle.read()
	if not raw:
		raw = os.getenv('PROXY_SHARE_LINKS', '')

	nodes = parse_share_links(raw)
	if not nodes:
		print('[FAILED] 没有解析出任何可用的代理节点', file=sys.stderr)
		return 1

	config = build_config(nodes, listen=args.listen, port=args.port, test_url=args.test_url, group_tag=args.group_tag)
	payload = json.dumps(config, ensure_ascii=False, indent=2) + '\n'
	if args.output:
		with open(args.output, 'w', encoding='utf-8') as handle:
			handle.write(payload)
		_info(f'已生成 {len(nodes)} 个节点的配置: {args.output}')
	else:
		sys.stdout.write(payload)
	return 0


if __name__ == '__main__':  # pragma: no cover
	raise SystemExit(main())
