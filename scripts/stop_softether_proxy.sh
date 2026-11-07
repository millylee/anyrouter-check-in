#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${RUNNER_TEMP:-/tmp}/checkin-proxy/softether"
# Checking the directory works even when its contents are root-only.
[[ -d "${STATE_DIR}" ]] || exit 0
ROOT=()
if [[ "${EUID}" != 0 ]]; then
	ROOT=(sudo -n)
fi
"${ROOT[@]}" python3 "${SCRIPT_DIR}/../utils/softether.py" stop --state-dir "${STATE_DIR}"
