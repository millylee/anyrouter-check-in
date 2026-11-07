#!/usr/bin/env bash
# 代理入口：按优先级选择后端。
#
#   1. SOFTETHER_VPN_CONFIG -> SoftEther VPN
#   2. PROXY_SUBSCRIPTION_URL -> mihomo 订阅
#   3. PROXY_SHARE_LINKS -> sing-box 分享链接
#   4. CHECKIN_PROXY_URL -> 使用已有代理；均为空则直连
#
# 其它环境变量见 setup_mihomo_proxy.sh / setup_singbox_proxy.sh。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${SOFTETHER_VPN_CONFIG:-}" ]]; then
	echo '[INFO] Using SOFTETHER_VPN_CONFIG (highest priority)'
	exec bash "${SCRIPT_DIR}/setup_softether_proxy.sh"
fi

if [[ -n "${PROXY_SUBSCRIPTION_URL:-}" ]]; then
	if [[ -n "${PROXY_SHARE_LINKS:-}" ]]; then
		echo "[INFO] PROXY_SUBSCRIPTION_URL 与 PROXY_SHARE_LINKS 同时设置，使用 PROXY_SUBSCRIPTION_URL，忽略 PROXY_SHARE_LINKS"
	fi
	exec bash "${SCRIPT_DIR}/setup_mihomo_proxy.sh"
fi

if [[ -n "${PROXY_SHARE_LINKS:-}" ]]; then
	exec bash "${SCRIPT_DIR}/setup_singbox_proxy.sh"
fi

if [[ -n "${CHECKIN_PROXY_URL:-}" ]]; then
	echo '[INFO] Using existing CHECKIN_PROXY_URL'
else
	echo '[INFO] No proxy configured; using direct connections'
fi
