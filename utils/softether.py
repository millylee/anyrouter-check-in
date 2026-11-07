"""Linux SoftEther lifecycle. The application namespace has only a VPN uplink.

The client keeps the host's routes. A bridge joins its TAP to the namespace;
two local socat relays cross the namespace boundary over a private Unix socket.
No host default route, DNS setting, forwarding flag or firewall rule is changed.
"""

import argparse
import hashlib
import ipaddress
import json
import os
import platform
import re
import shlex
import shutil
import signal
import socket
import subprocess  # nosec B404 - Native Linux tools are required; commands never use a shell.
import sys
import tarfile
import tempfile
import time
from pathlib import Path

RELEASE = 'v4.44-9807-rtm'
ARCHIVE = f'softether-vpnclient-{RELEASE}-2025.04.16-linux-x64-64bit.tar.gz'
DOWNLOAD_URL = f'https://github.com/SoftEtherVPN/SoftEtherVPN_Stable/releases/download/{RELEASE}/{ARCHIVE}'
ARCHIVE_SHA256 = 'ec18be1da49dfe6f4e05dfded46206de20a353055de0338a921eaf9a8a7c6fc6'
ACCOUNT = 'checkin'


class SetupError(Exception):
	"""A diagnostic safe to print without revealing profile fields."""


def prepare_profile(raw: str, adapter: str) -> str:
	"""Preserve native fields/escaping; replace only local names and auto-start.

	SoftEther encodes whitespace in values as $xx. Credentials and certificate
	verification settings are deliberately left to the native AccountImport.
	"""
	text = raw.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
	if '\x00' in text or not text.strip():
		raise SetupError('SOFTETHER_VPN_CONFIG must contain the complete UTF-8 .vpn text')
	stack: list[str] = []
	pending = None
	sections: set[tuple[str, ...]] = set()
	fields: set[tuple[str, ...]] = set()
	output = []
	for line in text.splitlines():
		stripped = line.strip()
		if not stripped or stripped.startswith(('#', '//')):
			output.append(line)
			continue
		if stripped.startswith('declare '):
			parts = stripped.split()
			if pending or len(parts) != 2:
				raise SetupError('Invalid .vpn section declaration')
			pending = parts[1]
		elif stripped == '{':
			if not pending:
				raise SetupError('Invalid .vpn section opening')
			stack.append(pending)
			pending = None
			key = tuple(stack)
			if key in sections:
				raise SetupError('Duplicate .vpn section')
			sections.add(key)
		elif stripped == '}':
			if pending or not stack:
				raise SetupError('Invalid .vpn section closing')
			if stack == ['root'] and ('root', 'StartupAccount') not in fields:
				output.append('\tbool StartupAccount false')
			stack.pop()
		else:
			parts = stripped.split(maxsplit=2)
			if pending or not stack or len(parts) != 3:
				raise SetupError('Invalid .vpn field; paste the file without JSON or Base64 encoding')
			kind, name, value = parts
			key = (*stack, name)
			if key in fields:
				raise SetupError('Duplicate .vpn field')
			fields.add(key)
			if key in {('root', 'ClientOption', 'AccountName'), ('root', 'ClientOption', 'DeviceName')}:
				value = ACCOUNT if name == 'AccountName' else adapter
				line = f'\t\tstring {name} {value}'
			elif key == ('root', 'StartupAccount'):
				line = '\tbool StartupAccount false'
			elif key == ('root', 'ClientAuth', 'AuthType') and value not in {'0', '1', '2', '3'}:
				raise SetupError('Smart-card/engine authentication cannot be used by this unattended Linux client')
		output.append(line)
	required = {
		('root', 'ClientOption', 'AccountName'),
		('root', 'ClientOption', 'DeviceName'),
		('root', 'ClientOption', 'Hostname'),
		('root', 'ClientOption', 'Port'),
		('root', 'ClientOption', 'HubName'),
		('root', 'ClientAuth', 'AuthType'),
	}
	if stack or pending or ('root',) not in sections or not required <= fields:
		raise SetupError('Incomplete .vpn profile: export a single connection with its authentication information')
	if any(section[0] != 'root' for section in sections):
		raise SetupError('Expected one .vpn root section')
	return '\n'.join(output) + '\n'


def run(*args: str, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess:
	# Never print command output: vpncmd can echo account/server/credential data.
	return subprocess.run(  # nosec B603 - Internal argv only; profile text is not interpolated into commands.
		args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=check
	)


def process_info(pid: int) -> tuple[int, str]:
	"""Return process group and start time; zombies no longer own resources."""
	try:
		fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
		return (int(fields[2]), fields[19]) if fields[0] not in {'Z', 'X'} else (0, '')
	except (OSError, IndexError, ValueError):
		return 0, ''


def process_birth(pid: int) -> str:
	return process_info(pid)[1]


def write_private(path: Path, content: str) -> None:
	path.write_text(content, encoding='utf-8')
	path.chmod(0o600)


def ensure_dependencies() -> None:
	packages = {
		'ip': 'iproute2',
		'curl': 'curl',
		'make': 'make',
		'gcc': 'gcc',
		'tinyproxy': 'tinyproxy-bin',
		'socat': 'socat',
		'udhcpc': 'udhcpc',
	}
	missing = [package for command, package in packages.items() if not shutil.which(command)]
	if missing:
		if not shutil.which('apt-get'):
			raise SetupError('SoftEther auto-install requires Ubuntu/Debian with apt-get')
		print('[INFO] Installing SoftEther system dependencies...', flush=True)
		run('apt-get', 'update', '-qq', timeout=180)
		run('apt-get', 'install', '-y', '--no-install-recommends', *missing, timeout=300)


class Runtime:
	def __init__(self, state_dir: Path):
		self.state_dir = state_dir
		self.runtime: Path | None = None
		self.state: dict = {}
		self.children: list[subprocess.Popen] = []

	def save(self) -> None:
		write_private(self.state_dir / 'state.json', json.dumps(self.state))

	def start(self, *args: str, env: dict | None = None) -> None:
		child = subprocess.Popen(  # nosec B603 - Fixed tools or verified binaries, with argv and no shell.
			args,
			stdin=subprocess.DEVNULL,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			start_new_session=True,
			env=env,
		)
		self.children.append(child)
		self.state['processes'].append([child.pid, process_birth(child.pid)])
		self.save()

	def wait(self, predicate, seconds: int, diagnostic: str) -> None:
		deadline = time.monotonic() + seconds
		while time.monotonic() < deadline:
			if any(child.poll() is not None for child in self.children):
				raise SetupError(f'{diagnostic}: a required process stopped')
			if predicate():
				return
			time.sleep(1)
		raise SetupError(diagnostic)

	def setup(self, raw: str, port: int, test_url: str) -> None:
		profile = prepare_profile(raw, 'checkin')
		if platform.system() != 'Linux' or platform.machine() not in {'x86_64', 'amd64'}:
			raise SetupError('SoftEther automatic setup currently supports Linux x86_64 only')
		if not Path('/dev/net/tun').exists():
			raise SetupError('SoftEther requires /dev/net/tun and permission to create TAP devices')
		if not 1024 <= port <= 65535:
			raise SetupError('PROXY_PORT must be between 1024 and 65535')
		if not test_url.startswith(('http://', 'https://')):
			raise SetupError('PROXY_TEST_URL must be an HTTP(S) URL')
		# Refuse to control an existing system client or an occupied proxy port.
		for check_port in (9930, port):
			with socket.socket() as probe:
				probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				try:
					probe.bind(('127.0.0.1', check_port))
				except OSError as exc:
					raise SetupError(
						f'Local port {check_port} is already occupied; stop the existing service first'
					) from exc
		ensure_dependencies()
		self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
		self.runtime = Path(tempfile.mkdtemp(prefix='checkin-se-', dir='/run'))
		token = self.runtime.name.removeprefix('checkin-se-')
		ns, bridge, peer, adapter = f'ci-se-{token}', f'cb{token}', f'cv{token}', f'c{token}'
		self.state = {
			'runtime': str(self.runtime),
			'namespace': ns,
			'bridge': bridge,
			'peer': peer,
			'processes': [],
			'namespace_created': False,
			'bridge_created': False,
			'peer_created': False,
		}
		self.save()
		profile = prepare_profile(profile, adapter)
		root = self.runtime
		print(f'[INFO] Preparing SoftEther {RELEASE}...', flush=True)
		archive = root / 'client.tar.gz'
		run(
			'curl',
			'-fLsS',
			'--retry',
			'3',
			'--connect-timeout',
			'15',
			'--max-time',
			'120',
			'-o',
			str(archive),
			DOWNLOAD_URL,
			timeout=500,
		)
		if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
			raise SetupError('SoftEther archive checksum mismatch')
		with tarfile.open(archive) as bundle:
			# The archive is pinned above; extraction is additionally restricted.
			bundle.extractall(root, filter='data')
		client = root / 'vpnclient'
		run('make', '-C', str(client), timeout=120)
		write_private(
			client / 'vpn_client.config',
			'declare root\n{\n declare Config\n {\n  bool AllowRemoteConfig false\n  bool UseKeepConnect false\n }\n}\n',
		)
		write_private(root / 'account.vpn', profile)
		self.start(str(client / 'vpnclient'), 'execsvc')

		def vpncmd(*args: str, check: bool = True):
			return run(str(client / 'vpncmd'), '127.0.0.1:9930', '/CLIENT', '/CMD', *args, check=check)

		self.wait(lambda: vpncmd('NicList', check=False).returncode == 0, 30, 'SoftEther client did not start')
		vpncmd('RemoteDisable')
		vpncmd('NicCreate', adapter)
		# vpncmd treats /name as an option; // escapes an absolute positional path.
		vpncmd('AccountImport', '/' + str(root / 'account.vpn'))
		(root / 'account.vpn').unlink()
		vpncmd('AccountNicSet', ACCOUNT, f'/NICNAME:{adapter}')
		vpncmd('AccountStartupRemove', ACCOUNT)
		vpncmd('AccountRetrySet', ACCOUNT, '/NUM:999', '/INTERVAL:5')
		tap = f'vpn_{adapter}'
		self.wait(lambda: Path(f'/sys/class/net/{tap}').exists(), 15, 'SoftEther virtual adapter was not created')

		run('ip', 'netns', 'add', ns)
		self.state['namespace_created'] = True
		self.save()
		resolver_dir = Path('/etc/netns') / ns
		resolver_dir.mkdir(parents=True)
		# No host resolver fallback. DHCP overwrites this file in place so all
		# already-running processes retain the correct bind-mounted resolver.
		(resolver_dir / 'resolv.conf').write_text('nameserver 127.0.0.1\n', encoding='ascii')
		self.state['resolver_created'] = True
		self.save()
		run(
			'ip',
			'netns',
			'exec',
			ns,
			'sysctl',
			'-qw',
			'net.ipv6.conf.all.disable_ipv6=1',
			'net.ipv6.conf.default.disable_ipv6=1',
		)
		run('ip', 'link', 'add', bridge, 'type', 'bridge')
		self.state['bridge_created'] = True
		self.save()
		run('ip', 'link', 'add', peer, 'type', 'veth', 'peer', 'name', 'vpn0', 'netns', ns)
		self.state['peer_created'] = True
		self.save()
		# Keep the namespace MAC distinct from the bridge's local port MACs;
		# otherwise Linux would consume replies locally instead of forwarding.
		for interface in (bridge, peer, tap):
			ipv6 = Path(f'/proc/sys/net/ipv6/conf/{interface}/disable_ipv6')
			if ipv6.exists():
				ipv6.write_text('1')
			if interface != bridge:
				run('ip', 'link', 'set', interface, 'master', bridge)
			run('ip', 'link', 'set', interface, 'up')
		run('ip', '-n', ns, 'link', 'set', 'lo', 'up')
		run('ip', '-n', ns, 'link', 'set', 'vpn0', 'up')
		hook = root / 'dhcp-hook'
		hook.write_text(
			'#!/bin/sh\nexec '
			+ shlex.join(
				[sys.executable, str(Path(__file__).resolve()), 'dhcp', '--runtime', str(root), '--namespace', ns]
			)
			+ ' "$1"\n',
			encoding='utf-8',
		)
		hook.chmod(0o700)
		print('[INFO] Connecting imported profile and waiting for VPN DHCP/DNS...', flush=True)
		vpncmd('AccountConnect', ACCOUNT)
		self.start('ip', 'netns', 'exec', ns, 'udhcpc', '-f', '-i', 'vpn0', '-s', str(hook), '-t', '5', '-T', '3')
		self.wait(
			lambda: (root / 'lease.ready').exists(),
			120,
			'VPN DHCP/DNS unavailable: check exported credentials, server DHCP and Internet access',
		)
		proxy_config = root / 'tinyproxy.conf'
		write_private(
			proxy_config,
			f'Port {port}\nListen 127.0.0.1\nTimeout 30\nMaxClients 64\n'
			'Allow 127.0.0.1\nUser nobody\nGroup nogroup\nLogFile "/dev/null"\nLogLevel Error\n'
			'DisableViaHeader Yes\n',
		)
		self.start('ip', 'netns', 'exec', ns, 'tinyproxy', '-d', '-c', str(proxy_config))
		unix_socket = root / 'proxy.sock'
		self.start(
			'ip', 'netns', 'exec', ns, 'socat', f'UNIX-LISTEN:{unix_socket},fork,mode=0600', f'TCP4:127.0.0.1:{port}'
		)
		self.wait(unix_socket.exists, 10, 'SoftEther Unix relay did not start')
		self.start('socat', f'TCP4-LISTEN:{port},bind=127.0.0.1,reuseaddr,fork', f'UNIX-CONNECT:{unix_socket}')
		self.wait(
			lambda: (
				run(
					'curl',
					'--noproxy',
					'',
					'-fLsS',
					'-x',
					f'http://127.0.0.1:{port}',
					'--connect-timeout',
					'5',
					'--max-time',
					'10',
					test_url,
					'-o',
					'/dev/null',
					check=False,
				).returncode
				== 0
			),
			60,
			'SoftEther proxy HTTPS health check failed',
		)
		print(f'[SUCCESS] SoftEther proxy is ready: http://127.0.0.1:{port}', flush=True)


def cleanup(state_dir: Path) -> None:
	state_file = state_dir / 'state.json'
	if not state_file.exists():
		return
	state = json.loads(state_file.read_text())
	root = Path(state['runtime'])
	# Only remove private resources made by this helper, including on failure.
	if root.parent != Path('/run') or not re.fullmatch(r'checkin-se-[a-z0-9_]{8}', root.name):
		raise SetupError('Refusing cleanup of an unrecognized SoftEther runtime')
	if root.is_symlink() or (root.exists() and root.stat().st_uid != 0):
		raise SetupError('Refusing cleanup of an unowned SoftEther runtime')
	token = root.name.removeprefix('checkin-se-')
	ns, bridge, peer = f'ci-se-{token}', f'cb{token}', f'cv{token}'
	processes = state.get('processes', [])
	groups = {pid for pid, birth in processes if birth and process_birth(pid) == birth}
	# execsvc has a supervisor and a service child. Capture every group member
	# before TERM, so a supervisor exiting early cannot hide a surviving child.
	members = {}
	for entry in Path('/proc').iterdir():
		if entry.name.isdecimal():
			pid = int(entry.name)
			group, birth = process_info(pid)
			if group in groups and birth:
				members[pid] = birth
	for group in groups:
		try:
			os.killpg(group, signal.SIGTERM)
		except ProcessLookupError:
			pass
	deadline = time.monotonic() + 5
	while time.monotonic() < deadline and any(process_birth(pid) == birth for pid, birth in members.items()):
		time.sleep(0.1)
	for pid, birth in members.items():
		if process_birth(pid) == birth:
			try:
				os.kill(pid, signal.SIGKILL)
			except ProcessLookupError:
				pass
	deadline = time.monotonic() + 2
	while time.monotonic() < deadline and any(process_birth(pid) == birth for pid, birth in members.items()):
		time.sleep(0.1)
	if state.get('peer_created'):
		run('ip', 'link', 'del', peer, check=False)
	if state.get('bridge_created'):
		run('ip', 'link', 'del', bridge, check=False)
	if state.get('namespace_created'):
		run('ip', 'netns', 'del', ns, check=False)
	if state.get('resolver_created'):
		shutil.rmtree(Path('/etc/netns') / ns)
	if root.exists():
		shutil.rmtree(root)
	state_file.unlink()
	state_dir.rmdir()


def dhcp_lease(env: dict[str, str]) -> tuple[str, str, list[str]]:
	"""Validate DHCP data before using it in commands or resolver files."""
	try:
		address = ipaddress.IPv4Interface(f'{env["ip"]}/{env["subnet"]}')
		gateway = ipaddress.IPv4Address(env['router'].split()[0])
		dns = [str(ipaddress.IPv4Address(value)) for value in env['dns'].split()]
		if address.network.prefixlen == 0 or gateway not in address.network or not dns:
			raise ValueError
		if any(ipaddress.ip_address(value).is_loopback or ipaddress.ip_address(value).is_unspecified for value in dns):
			raise ValueError
	except (KeyError, ValueError, IndexError) as exc:
		raise SetupError('VPN DHCP must supply an IPv4 address, subnet, on-link router and DNS servers') from exc
	return str(address), str(gateway), dns


def dhcp_event(event: str, runtime: Path, namespace: str) -> None:
	if os.environ.get('interface') != 'vpn0':
		raise SetupError('Unexpected DHCP interface')
	ready = runtime / 'lease.ready'
	resolver = Path('/etc/netns') / namespace / 'resolv.conf'
	if event in {'deconfig', 'nak', 'leasefail'}:
		ready.unlink(missing_ok=True)
		run('ip', '-4', 'route', 'flush', 'dev', 'vpn0')
		run('ip', '-4', 'addr', 'flush', 'dev', 'vpn0')
		resolver.write_text('nameserver 127.0.0.1\n', encoding='ascii')
	elif event in {'bound', 'renew'}:
		address, gateway, dns = dhcp_lease(dict(os.environ))
		run('ip', '-4', 'addr', 'flush', 'dev', 'vpn0')
		run('ip', '-4', 'addr', 'add', address, 'dev', 'vpn0')
		run('ip', '-4', 'route', 'replace', 'default', 'via', gateway, 'dev', 'vpn0')
		resolver.write_text(
			''.join(f'nameserver {value}\n' for value in dns) + 'options timeout:2 attempts:2\n', encoding='ascii'
		)
		write_private(ready, 'ready\n')


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	commands = parser.add_subparsers(dest='command', required=True)
	setup = commands.add_parser('setup')
	setup.add_argument('--state-dir', type=Path, required=True)
	setup.add_argument('--port', type=int, default=7890)
	setup.add_argument('--test-url', default='https://www.google.com/generate_204')
	stop = commands.add_parser('stop')
	stop.add_argument('--state-dir', type=Path, required=True)
	dhcp = commands.add_parser('dhcp')
	dhcp.add_argument('--runtime', type=Path, required=True)
	dhcp.add_argument('--namespace', required=True)
	dhcp.add_argument('event')
	args = parser.parse_args()
	if platform.system() != 'Linux' or os.geteuid() != 0:
		print('[FAILED] SoftEther network setup requires Linux root / passwordless sudo', file=sys.stderr)
		return 1
	manager = None
	try:
		if args.command == 'setup':
			os.environ.pop('SOFTETHER_VPN_CONFIG', None)
			manager = Runtime(args.state_dir)

			def interrupted(signum, frame):
				raise SetupError('SoftEther setup interrupted')

			signal.signal(signal.SIGTERM, interrupted)
			signal.signal(signal.SIGINT, interrupted)
			manager.setup(sys.stdin.read(), args.port, args.test_url)
		elif args.command == 'stop':
			cleanup(args.state_dir)
		else:
			dhcp_event(args.event, args.runtime, args.namespace)
		return 0
	except Exception as exc:
		# Only our fixed messages are safe. Native errors may contain secrets.
		message = str(exc) if isinstance(exc, SetupError) else f'SoftEther {args.command} failed ({type(exc).__name__})'
		print(f'[FAILED] {message}', file=sys.stderr)
		if manager and manager.runtime:
			cleanup(args.state_dir)
		return 1


if __name__ == '__main__':
	sys.exit(main())
