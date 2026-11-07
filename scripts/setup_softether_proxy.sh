#!/usr/bin/env bash
# SOFTETHER_VPN_CONFIG: verbatim UTF-8 .vpn export, including authentication.
# Linux x86_64 with root/passwordless sudo. No global proxy or route changes.
set -euo pipefail
set +x

[[ -n "${SOFTETHER_VPN_CONFIG:-}" ]] || exit 0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${RUNNER_TEMP:-/tmp}/checkin-proxy/softether"
PROXY_PORT="${PROXY_PORT:-7890}"
PROXY_TEST_URL="${PROXY_TEST_URL:-https://www.google.com/generate_204}"

fail() {
	echo '[FAILED] SoftEther setup failed; no lower-priority backend will be attempted'
	# A selected backend failure must not silently reuse a lower-priority proxy.
	if [[ -n "${GITHUB_ENV:-}" ]]; then
		echo 'CHECKIN_PROXY_URL=' >> "${GITHUB_ENV}"
	fi
	[[ "${PROXY_REQUIRED:-false}" != 'true' ]] && exit 0
	exit 1
}

[[ "$(uname -s)" == 'Linux' ]] || { echo '[FAILED] SoftEther requires Linux'; fail; }
command -v python3 >/dev/null || { echo '[FAILED] python3 is required'; fail; }
mkdir -p "$(dirname "${STATE_DIR}")"
ROOT=()
if [[ "${EUID}" != 0 ]]; then
	ROOT=(sudo -n)
	"${ROOT[@]}" true || fail
fi

# Pass the profile through stdin, not command arguments or sudo's environment.
if ! printf '%s' "${SOFTETHER_VPN_CONFIG}" | "${ROOT[@]}" python3 "${SCRIPT_DIR}/../utils/softether.py" setup \
	--state-dir "${STATE_DIR}" --port "${PROXY_PORT}" --test-url "${PROXY_TEST_URL}"; then
	fail
fi
if [[ -n "${GITHUB_ENV:-}" ]]; then
	printf 'CHECKIN_PROXY_URL=http://127.0.0.1:%s\n' "${PROXY_PORT}" >> "${GITHUB_ENV}"
fi
