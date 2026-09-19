#!/usr/bin/env bash
# 代理入口：按优先级选择后端。
#
#   1. PROXY_SUBSCRIPTION_URL 有值 -> mihomo 拉订阅（此时忽略 PROXY_SHARE_LINKS）
#   2. 否则 PROXY_SHARE_LINKS 有值 -> sing-box 用分享链接
#   3. 都没有 -> 不配置代理
#
# 其它环境变量见 setup_mihomo_proxy.sh / setup_singbox_proxy.sh。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${PROXY_SUBSCRIPTION_URL:-}" ]]; then
	if [[ -n "${PROXY_SHARE_LINKS:-}" ]]; then
		echo "[INFO] PROXY_SUBSCRIPTION_URL 与 PROXY_SHARE_LINKS 同时设置，使用 PROXY_SUBSCRIPTION_URL，忽略 PROXY_SHARE_LINKS"
	fi
	exec bash "${SCRIPT_DIR}/setup_mihomo_proxy.sh"
fi

if [[ -n "${PROXY_SHARE_LINKS:-}" ]]; then
	exec bash "${SCRIPT_DIR}/setup_singbox_proxy.sh"
fi

echo "[INFO] PROXY_SUBSCRIPTION_URL / PROXY_SHARE_LINKS 均未设置，skip proxy setup"
