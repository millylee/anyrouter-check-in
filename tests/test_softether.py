"""Profile portability, DHCP validation and backend selection without a live VPN."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from utils.softether import SetupError, dhcp_lease, prepare_profile, process_info

PROFILE = """# SoftEther VPN Client connection setting
declare root
{
 bool CheckServerCert true
 byte ServerCert cHJlc2VydmUtbWU=
 bool StartupAccount true
 declare ClientAuth
 {
  uint AuthType 1
  string Username name$20with$20spaces
  byte HashedPassword c2VjcmV0LXZhbHVl
 }
 declare ClientOption
 {
  string AccountName Windows$20connection
  string DeviceName VPN
  string Hostname vpn.example.com
  uint Port 443
  string HubName DEFAULT
 }
}
"""


def test_native_profile_preserves_authentication_and_verification():
	result = prepare_profile('\ufeff' + PROFILE.replace('\n', '\r\n'), 'c12345678')
	assert '\r' not in result and '\ufeff' not in result
	assert 'string AccountName checkin' in result
	assert 'string DeviceName c12345678' in result
	assert 'bool StartupAccount false' in result
	for field in (
		'bool CheckServerCert true',
		'byte ServerCert cHJlc2VydmUtbWU=',
		'byte HashedPassword c2VjcmV0LXZhbHVl',
		'string Username name$20with$20spaces',
	):
		assert field in result


def test_profile_without_startup_flag_gets_disabled_before_import():
	result = prepare_profile(PROFILE.replace(' bool StartupAccount true\n', ''), 'test')
	assert result.count('bool StartupAccount false') == 1


@pytest.mark.parametrize(
	'text',
	[
		'',
		'not a profile',
		PROFILE[:-3],
		PROFILE + PROFILE,
		PROFILE.replace('uint Port 443', 'uint Port 443\n uint Port 80'),
		PROFILE.replace('  string Hostname vpn.example.com\n', ''),
		PROFILE + '\x00',
	],
)
def test_invalid_profiles_fail_without_echoing_content(text):
	with pytest.raises(SetupError) as error:
		prepare_profile(text, 'test')
	assert 'c2VjcmV0' not in str(error.value)
	assert 'vpn.example.com' not in str(error.value)


def test_smartcard_authentication_has_actionable_error():
	with pytest.raises(SetupError, match='Smart-card'):
		prepare_profile(PROFILE.replace('AuthType 1', 'AuthType 4'), 'test')


LEASE = {'ip': '192.168.30.10', 'subnet': '255.255.255.0', 'router': '192.168.30.1', 'dns': '192.168.30.1 1.1.1.1'}


def test_dhcp_lease_accepts_valid_ipv4_network():
	assert dhcp_lease(LEASE) == ('192.168.30.10/24', '192.168.30.1', ['192.168.30.1', '1.1.1.1'])


@pytest.mark.parametrize(
	'field,value',
	[
		('ip', 'bad'),
		('subnet', '0.0.0.0'),
		('router', ''),
		('router', '10.0.0.1'),
		('dns', ''),
		('dns', '127.0.0.53'),
		('dns', '0.0.0.0'),
		('dns', '1.1.1.1\nnameserver evil'),
	],
)
def test_dhcp_missing_or_invalid_data_cannot_create_a_ready_proxy(field, value):
	with pytest.raises(SetupError, match='DHCP'):
		dhcp_lease(dict(LEASE, **{field: value}))


@pytest.mark.parametrize('state,expected', [('S', (42, '1234')), ('Z', (0, '')), ('X', (0, ''))])
def test_cleanup_process_identity_handles_spaces_parentheses_and_zombies(monkeypatch, state, expected):
	fields = [state, '1', '42', *(['0'] * 16), '1234']
	monkeypatch.setattr(Path, 'read_text', lambda self: '99 (name with ) spaces) ' + ' '.join(fields))
	assert process_info(99) == expected


@pytest.mark.skipif(os.name == 'nt' or not shutil.which('bash'), reason='requires POSIX bash')
@pytest.mark.parametrize(
	'configured,expected',
	[
		(
			{
				'SOFTETHER_VPN_CONFIG': 'sensitive-profile',
				'PROXY_SUBSCRIPTION_URL': 'subscription',
				'PROXY_SHARE_LINKS': 'link',
				'CHECKIN_PROXY_URL': 'http://existing',
			},
			'softether',
		),
		({'PROXY_SUBSCRIPTION_URL': 'subscription', 'PROXY_SHARE_LINKS': 'link'}, 'mihomo'),
		({'PROXY_SHARE_LINKS': 'link'}, 'singbox'),
		({'CHECKIN_PROXY_URL': 'http://existing'}, 'existing'),
		({}, 'direct'),
	],
)
def test_backend_priority_runs_only_selected_backend(tmp_path, configured, expected):
	source = Path(__file__).resolve().parents[1] / 'scripts' / 'setup_proxy.sh'
	shutil.copy(source, tmp_path / source.name)
	for backend in ('softether', 'mihomo', 'singbox'):
		(tmp_path / f'setup_{backend}_proxy.sh').write_text(f'echo selected={backend}\nexit 17\n')
	env = {
		key: value
		for key, value in os.environ.items()
		if key not in {'SOFTETHER_VPN_CONFIG', 'PROXY_SUBSCRIPTION_URL', 'PROXY_SHARE_LINKS', 'CHECKIN_PROXY_URL'}
	}
	result = subprocess.run(
		['bash', str(tmp_path / source.name)], env=dict(env, **configured), capture_output=True, text=True
	)
	assert 'sensitive-profile' not in result.stdout
	if expected in {'softether', 'mihomo', 'singbox'}:
		assert result.returncode == 17  # No fallback after a selected backend fails.
		assert result.stdout.count('selected=') == 1
		assert f'selected={expected}' in result.stdout
	else:
		assert result.returncode == 0
		assert ('existing CHECKIN_PROXY_URL' if expected == 'existing' else 'direct connections') in result.stdout


@pytest.mark.skipif(os.name == 'nt' or not shutil.which('bash'), reason='requires POSIX bash')
@pytest.mark.parametrize('required,exit_code', [('false', 0), ('true', 1)])
def test_setup_failure_clears_actions_proxy_and_honors_required(tmp_path, required, exit_code):
	"""Exercise the shell failure contract without root, downloads or a VPN."""
	script = Path(__file__).resolve().parents[1] / 'scripts' / 'setup_softether_proxy.sh'
	bin_dir = tmp_path / 'bin'
	bin_dir.mkdir()
	stubs = {
		'python3': '#!/bin/sh\ncat >/dev/null\nexit 42\n',
		'sudo': '#!/bin/sh\nshift\nexec "$@"\n',
		'uname': '#!/bin/sh\necho Linux\n',
	}
	for name, contents in stubs.items():
		path = bin_dir / name
		path.write_text(contents)
		path.chmod(0o755)
	env_file = tmp_path / 'github.env'
	env = dict(
		os.environ,
		PATH=f'{bin_dir}:{os.environ["PATH"]}',
		RUNNER_TEMP=str(tmp_path),
		GITHUB_ENV=str(env_file),
		SOFTETHER_VPN_CONFIG='sensitive-profile-with-credentials',
		CHECKIN_PROXY_URL='http://lower-priority-proxy',
		PROXY_REQUIRED=required,
	)
	result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
	assert result.returncode == exit_code
	assert env_file.read_text() == 'CHECKIN_PROXY_URL=\n'
	assert 'no lower-priority backend' in result.stdout
	assert 'sensitive-profile-with-credentials' not in result.stdout + result.stderr
