#!/usr/bin/env bash
# 通过 sing-box 使用 Xray 分享链接启动本地代理并探测可用节点。
# 环境变量:
#   PROXY_SHARE_LINKS  分享链接，按行分隔，一个或多个（必填才启用）
#                      支持 vless:// vmess:// trojan:// ss:// hy2://
#   PROXY_TEST_URL     探测目标，默认 https://www.google.com/generate_204
#   PROXY_REQUIRED     true 时探测失败则退出 1
#   PROXY_PORT         本地 mixed 端口（HTTP/SOCKS 共用），默认 7890
#   SINGBOX_VERSION    sing-box 版本，默认 v1.14.1
#   PYTHON_BIN         生成配置用的 Python，默认自动探测 python3 / python

set -euo pipefail

if [[ -z "${PROXY_SHARE_LINKS:-}" ]]; then
	echo "[INFO] PROXY_SHARE_LINKS not set, skip sing-box proxy setup"
	exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROXY_DIR="${RUNNER_TEMP:-/tmp}/checkin-proxy"
PROXY_PORT="${PROXY_PORT:-7890}"
PROXY_TEST_URL="${PROXY_TEST_URL:-https://www.google.com/generate_204}"
SINGBOX_VERSION="${SINGBOX_VERSION:-v1.14.1}"
PROXY_REQUIRED="${PROXY_REQUIRED:-false}"
VERSION="${SINGBOX_VERSION#v}"

# 失败时按 PROXY_REQUIRED 决定是中断 workflow 还是放行（不设代理继续签到）
fail() {
	echo "[FAILED] $1"
	if [[ "${PROXY_REQUIRED}" == "true" ]]; then
		exit 1
	fi
	exit 0
}

# 按 uname 选择发行包，避免在非 linux/amd64 的机器上下到跑不起来的二进制。
# 只映射 sing-box 官方确实发布了的组合，其余直接报错而不是猜。
detect_platform() {
	local kernel arch
	kernel="$(uname -s)"
	arch="$(uname -m)"
	case "${kernel}" in
		Linux) OS='linux' ;;
		Darwin) OS='darwin' ;;
		MINGW* | MSYS* | CYGWIN*) OS='windows' ;;
		*) fail "不支持的操作系统: ${kernel}（请自行启动代理并设置 CHECKIN_PROXY_URL）" ;;
	esac
	case "${arch}" in
		x86_64 | amd64) ARCH='amd64' ;;
		aarch64 | arm64) ARCH='arm64' ;;
		armv7*) ARCH='armv7' ;;
		i386 | i686) ARCH='386' ;;
		riscv64) ARCH='riscv64' ;;
		*) fail "不支持的 CPU 架构: ${arch}" ;;
	esac

	if [[ "${OS}" == 'windows' ]]; then
		# windows 只有 zip，且没有 armv7 / riscv64
		if [[ "${ARCH}" != 'amd64' && "${ARCH}" != 'arm64' && "${ARCH}" != '386' ]]; then
			fail "sing-box 没有 windows-${ARCH} 发行包"
		fi
		ARCHIVE="sing-box-${VERSION}-windows-${ARCH}.zip"
		BIN_NAME='sing-box.exe'
	else
		if [[ "${OS}" == 'darwin' && "${ARCH}" != 'amd64' && "${ARCH}" != 'arm64' ]]; then
			fail "sing-box 没有 darwin-${ARCH} 发行包"
		fi
		ARCHIVE="sing-box-${VERSION}-${OS}-${ARCH}.tar.gz"
		BIN_NAME='sing-box'
	fi
}

# 生成配置只用标准库，但 python3 在部分 Windows 上是 Microsoft Store 的占位程序，
# 必须真的跑一次才算可用，否则 command -v 会选中一个打不开的解释器
detect_python() {
	if [[ -n "${PYTHON_BIN:-}" ]]; then
		printf '%s' "${PYTHON_BIN}"
		return
	fi
	local candidate
	for candidate in python3 python; do
		if command -v "${candidate}" >/dev/null 2>&1 && "${candidate}" -c 'import sys' >/dev/null 2>&1; then
			printf '%s' "${candidate}"
			return
		fi
	done
	printf ''
}

detect_platform
PYTHON_BIN="$(detect_python)"
if [[ -z "${PYTHON_BIN}" ]]; then
	fail "找不到可用的 python3 / python，无法生成 sing-box 配置"
fi
echo "[INFO] Using ${PYTHON_BIN} ($("${PYTHON_BIN}" -c 'import sys; print(sys.version.split()[0])'))"

mkdir -p "${PROXY_DIR}"
cd "${PROXY_DIR}"

# 分享链接里含密码，落盘的临时文件收紧权限并用完即删
echo "[INFO] Generating sing-box config from PROXY_SHARE_LINKS..."
umask 077
printf '%s' "${PROXY_SHARE_LINKS}" > links.txt
if ! (cd "${REPO_ROOT}" && "${PYTHON_BIN}" -m utils.singbox \
	--links-file "${PROXY_DIR}/links.txt" \
	--port "${PROXY_PORT}" \
	--test-url "${PROXY_TEST_URL}" \
	-o "${PROXY_DIR}/config.json"); then
	rm -f links.txt
	fail "Failed to build sing-box config from PROXY_SHARE_LINKS"
fi
rm -f links.txt

echo "[INFO] Downloading sing-box ${SINGBOX_VERSION} (${OS}-${ARCH})..."
if ! curl --retry 3 --retry-delay 5 --retry-all-errors -fsSL -o "${ARCHIVE}" \
	"https://github.com/SagerNet/sing-box/releases/download/${SINGBOX_VERSION}/${ARCHIVE}"; then
	echo "[WARN] Failed to download sing-box ${SINGBOX_VERSION} (${ARCHIVE})"
	fail "Failed to download sing-box ${SINGBOX_VERSION}"
fi
if [[ "${ARCHIVE}" == *.zip ]]; then
	if ! command -v unzip >/dev/null 2>&1; then
		fail "解压 ${ARCHIVE} 需要 unzip，当前环境没有安装"
	fi
	unzip -o -q "${ARCHIVE}"
else
	tar -xzf "${ARCHIVE}"
fi

# 用 shell glob 定位二进制，不依赖 GNU find 的 -print -quit（BSD/macOS 的 find 没有）
SINGBOX_BIN=''
for candidate in "sing-box-${VERSION}-${OS}-${ARCH}/${BIN_NAME}" "${BIN_NAME}" sing-box-*/"${BIN_NAME}"; do
	if [[ -f "${candidate}" ]]; then
		SINGBOX_BIN="${candidate}"
		break
	fi
done
if [[ -z "${SINGBOX_BIN}" ]]; then
	fail "sing-box binary not found in ${ARCHIVE}"
fi
chmod +x "${SINGBOX_BIN}"

echo "[INFO] Validating sing-box config..."
if ! "${SINGBOX_BIN}" check -c config.json; then
	# 不打印 config.json：里面有节点密码
	fail "sing-box config validation failed"
fi

echo "[INFO] Starting sing-box on 127.0.0.1:${PROXY_PORT}..."
nohup "${SINGBOX_BIN}" run -c config.json > singbox.log 2>&1 &
echo $! > singbox.pid

PROXY_URL="http://127.0.0.1:${PROXY_PORT}"
READY=false
for attempt in $(seq 1 45); do
	if curl -fsS -x "${PROXY_URL}" --max-time 20 "${PROXY_TEST_URL}" -o /dev/null 2>/dev/null; then
		READY=true
		break
	fi
	echo "[INFO] Waiting for proxy health check (${attempt}/45)..."
	sleep 2
done

if [[ "${READY}" != "true" ]]; then
	echo "[FAILED] Proxy health check failed for ${PROXY_TEST_URL}"
	tail -n 30 singbox.log || true
	if [[ -f singbox.pid ]]; then
		kill "$(cat singbox.pid)" 2>/dev/null || true
		rm -f singbox.pid
	fi
	fail "sing-box proxy is not reachable"
fi

echo "[SUCCESS] Proxy is ready: ${PROXY_URL}"
echo "[INFO] Proxy is scoped to CHECKIN_PROXY_URL (browser/python only, not global HTTP_PROXY)"
if [[ -n "${GITHUB_ENV:-}" ]]; then
	echo "CHECKIN_PROXY_URL=${PROXY_URL}" >> "${GITHUB_ENV}"
fi
