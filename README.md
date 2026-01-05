# Any Router 多账号自动签到

多平台多账号自动签到工具，兼容 NewAPI/OneAPI 平台。内置 [Any Router](https://anyrouter.top/register?aff=gSsN)、Agent Router。推荐搭配 [Auo](https://github.com/millylee/auo) 实现 Claude Code Token 切换。

**功能**：多平台多账号 | 机器人通知 | WAF 绕过

## 快速开始

### 1. Fork 仓库并启用 Actions

Fork 本仓库 → `Actions` → 启用工作流

### 2. 获取账号凭证（F12 开发者工具）

**Session Cookie**：`Application` → `Cookies` → 复制 `session` 值（有效期约 1 个月）

![获取 cookies](./assets/request-session.png)

**API User**：`Network` → 筛选 `Fetch/XHR` → 找到 `New-Api-User` 请求头（5 位数）

![获取 api_user](./assets/request-api-user.png)

### 3. 配置环境变量

`Settings` → `Environments` → 新建 `production` 环境 → 添加 Secret `ANYROUTER_ACCOUNTS`：

**单账号配置**：
```json
[
  {
    "cookies": {"session": "你的session值"},
    "api_user": "你的api_user值"
  }
]
```

**多服务商配置**（同时使用 anyrouter 和 agentrouter）：
```json
[
  {
    "name": "主账号",
    "cookies": {"session": "你的session值"},
    "api_user": "你的api_user值"
  },
  {
    "name": "备用",
    "provider": "agentrouter",
    "cookies": {"session": "session值"},
    "api_user": "api_user值"
  }
]
```

**参数**：`cookies`、`api_user` 必需 | `provider` 默认 `anyrouter` | `name` 用于日志标识

### 4. 测试运行

`Actions` → "AnyRouter 自动签到" → `Run workflow` 手动触发

![运行结果](./assets/check-in.png)

**自动执行**：每 6 小时（GitHub Actions 延迟 1~1.5 小时）

## 高级配置

<details>
<summary><b>自定义 Provider</b></summary>

默认支持 `anyrouter`、`agentrouter`。其他平台添加环境变量 `PROVIDERS`：

**基础**（仅域名）：
```json
{
  "customrouter": {
    "domain": "https://custom.example.com"
  }
}
```

**完整**（含 WAF 绕过）：
```json
{
  "customrouter": {
    "domain": "https://custom.example.com",
    "sign_in_path": "/api/checkin",
    "api_user_key": "x-user-id",
    "bypass_method": "waf_cookies",
    "waf_cookie_names": ["acw_tc", "cdn_sec_tc"]
  }
}
```

**字段**：`domain` 必需 | `bypass_method` 可选（`"waf_cookies"` 或 `null`）| 其他见默认配置

</details>

<details>
<summary><b>通知配置</b></summary>

在 `production` 环境添加对应 Secret：

**邮箱 (SMTP)**：`EMAIL_USER`、`EMAIL_PASS`、`EMAIL_TO`（可选：`EMAIL_SENDER`、`CUSTOM_SMTP_SERVER`）

**机器人**：
- 钉钉：`DINGDING_WEBHOOK`
- 飞书：`FEISHU_WEBHOOK`
- 企业微信：`WEIXIN_WEBHOOK`
- PushPlus：`PUSHPLUS_TOKEN`
- Server酱：`SERVERPUSHKEY`
- Telegram：`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- Gotify：`GOTIFY_URL` + `GOTIFY_TOKEN`（可选：`GOTIFY_PRIORITY`）

</details>


## 本地开发

```bash
# 安装依赖与浏览器
uv sync --dev && uv run playwright install chromium

# .env 配置（JSON 单行格式）
# ANYROUTER_ACCOUNTS=[{"name":"账号1","cookies":{"session":"xxx"},"api_user":"12345"}]

# 运行 | 测试
uv run checkin.py
uv run pytest tests/
```

## 免责声明

仅供学习研究，使用前请遵守网站使用条款。
