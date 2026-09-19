#!/usr/bin/env bash
# 停止 setup_proxy.sh 启动的本地代理（mihomo / sing-box）。
set -euo pipefail

PROXY_DIR="${RUNNER_TEMP:-/tmp}/checkin-proxy"

for name in mihomo singbox; do
	PID_FILE="${PROXY_DIR}/${name}.pid"
	if [[ -f "${PID_FILE}" ]]; then
		echo "[INFO] Stopping ${name} proxy (pid $(cat "${PID_FILE}"))"
		kill "$(cat "${PID_FILE}")" 2>/dev/null || true
		rm -f "${PID_FILE}"
	fi
done
