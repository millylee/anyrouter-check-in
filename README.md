# Any Router 多账号自动签到

[![GitHub Actions](https://github.com/millylee/anyrouter-check-in/workflows/PR%20Quality%20Checks/badge.svg)](https://github.com/millylee/anyrouter-check-in/actions)
[![codecov](https://codecov.io/gh/millylee/anyrouter-check-in/branch/main/graph/badge.svg)](https://codecov.io/gh/millylee/anyrouter-check-in)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/millylee/anyrouter-check-in/main.svg)](https://results.pre-commit.ci/latest/github/millylee/anyrouter-check-in/main)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/github/license/millylee/anyrouter-check-in)](LICENSE)

多平台多账号自动签到，理论上支持所有 NewAPI、OneAPI 平台，目前内置支持 Any Router 与 Agent Router，其它可根据文档进行摸索配置。

推荐搭配使用[Auo](https://github.com/millylee/auo)，支持任意 Claude Code Token 切换的工具。

**维护开源不易，如果本项目帮助到了你，请帮忙点个 Star，谢谢!**

用于 Claude Code 中转站 Any Router 网站多账号每日签到，一次 $25，限时注册即送 100 美金，[点击这里注册](https://anyrouter.top/register?aff=gSsN)。业界良心，支持 Claude Sonnet 4.5、GPT-5-Codex、Claude Code 百万上下文（使用 `/model sonnet[1m]` 开启），`gemini-2.5-pro` 模型。

## 功能特性

- ✅ 多平台（兼容 NewAPI 与 OneAPI）
- ✅ 单个/多账号自动签到
- ✅ 多种机器人通知（可选）
- ✅ 绕过 WAF 限制

## 使用方法

### 1. Fork 本仓库

点击右上角的 "Fork" 按钮，将本仓库 fork 到你的账户。

### 2. 获取账号信息

对于每个需要签到的账号，你需要获取：(可借助 [在线 Secrets 配置生成器](https://millylee.github.io/anyrouter-check-in/))

1. **Cookies**: 用于身份验证
2. **API User**: 用于请求头的 new-api-user 参数（自己配置其它平台时该值需要注意匹配）

#### 获取 Cookies：

1. 打开浏览器，访问 https://anyrouter.top/
2. 登录你的账户
3. 打开开发者工具 (F12)
4. 切换到 "Application" 或 "存储" 选项卡
5. 找到 "Cookies" 选项
6. 复制所有 cookies

#### 获取 API User：

按照下方图片教程操作获得。

### 3. 设置 GitHub Environment Secret

1. 在你 fork 的仓库中，点击 "Settings" 选项卡
2. 在左侧菜单中找到 "Environments" -> "New environment"
3. 新建一个名为 `production` 的环境
4. 点击新建的 `production` 环境进入环境配置页
5. 点击 "Add environment secret" 创建 secret：
   - Name: `ANYROUTER_ACCOUNTS`
   - Value: 你的多账号配置数据

### 4. 多账号配置格式

支持单个与多个账号配置，可选 `name` 和 `provider` 字段：

```json
[
  {
    "name": "我的主账号",
    "cookies": {
      "session": "account1_session_value"
    },
    "api_user": "account1_api_user_id"
  },
  {
    "name": "备用账号",
    "provider": "agentrouter",
    "cookies": {
      "session": "account2_session_value"
    },
    "api_user": "account2_api_user_id"
  }
]
```

**字段说明**：

- `cookies` (必需)：用于身份验证的 cookies 数据
- `api_user` (必需)：用于请求头的 new-api-user 参数
- `provider` (可选)：指定使用的服务商，默认为 `anyrouter`
- `name` (可选)：自定义账号显示名称，用于通知和日志中标识账号

**默认值说明**：

- 如果未提供 `provider` 字段，默认使用 `anyrouter`（向后兼容）
- 如果未提供 `name` 字段，会使用 `Account 1`、`Account 2` 等默认名称
- `anyrouter` 与 `agentrouter` 配置已内置，无需填写

接下来获取 cookies 与 api_user 的值。

通过 F12 工具，切到 Application 面板，拿到 session 的值，最好重新登录下，该值 1 个月有效期，但有可能提前失效，失效后报 401 错误，到时请再重新获取。

![获取 cookies](./assets/request-session.png)

通过 F12 工具，切到 Network 面板，可以过滤下，只要 Fetch/XHR，找到带 `New-Api-User`，这个值正常是 5 位数，如果是负数或者个位数，正常是未登录。

![获取 api_user](./assets/request-api-user.png)

### 5. 启用 GitHub Actions

1. 在你的仓库中，点击 "Actions" 选项卡
2. 如果提示启用 Actions，请点击启用
3. 找到 "AnyRouter 自动签到" workflow
4. 点击 "Enable workflow"

### 6. 测试运行

你可以手动触发一次签到来测试：

1. 在 "Actions" 选项卡中，点击 "AnyRouter 自动签到"
2. 点击 "Run workflow" 按钮
3. 确认运行

![运行结果](./assets/check-in.png)

## 执行时间

- 脚本每 6 小时执行一次（1. action 无法准确触发，基本延时 1~1.5h；2. 目前观测到 anyrouter 的签到是每 24h 而不是零点就可签到）
- 你也可以随时手动触发签到

## 注意事项

- 请确保每个账号的 cookies 和 API User 都是正确的
- 可以在 Actions 页面查看详细的运行日志
- 支持部分账号失败，只要有账号成功签到，整个任务就不会失败
- 报 401 错误，请重新获取 cookies，理论 1 个月失效，但有 Bug，详见 [#6](https://github.com/millylee/anyrouter-check-in/issues/6)
- 请求 200，但出现 Error 1040（08004）：Too many connections，官方数据库问题，目前已修复，但遇到几次了，详见 [#7](https://github.com/millylee/anyrouter-check-in/issues/7)

## 配置示例

### 基础配置（向后兼容）

假设你有两个账号需要签到，不指定 provider 时默认使用 anyrouter：

```json
[
  {
    "cookies": {
      "session": "abc123session"
    },
    "api_user": "user123"
  },
  {
    "cookies": {
      "session": "xyz789session"
    },
    "api_user": "user456"
  }
]
```

### 多服务商配置

如果你需要同时使用多个服务商（如 anyrouter 和 agentrouter）：

```json
[
  {
    "name": "AnyRouter 主账号",
    "provider": "anyrouter",
    "cookies": {
      "session": "abc123session"
    },
    "api_user": "user123"
  },
  {
    "name": "AgentRouter 备用",
    "provider": "agentrouter",
    "cookies": {
      "session": "xyz789session"
    },
    "api_user": "user456"
  }
]
```

## 多行 JSON 支持

`ANYROUTER_ACCOUNTS` 和 `PROVIDERS` 环境变量现在支持多行 JSON 格式，无需手动压缩为单行。脚本会自动处理换行和缩进。

在 GitHub Secrets 中可以直接粘贴格式化后的 JSON：

```json
[
  {
    "name": "我的主账号",
    "cookies": {
      "session": "abc123session"
    },
    "api_user": "12345"
  },
  {
    "name": "备用账号",
    "provider": "agentrouter",
    "cookies": {
      "session": "xyz789session"
    },
    "api_user": "67890"
  }
]
```

不需要再通过在线配置生成器后手动转为一行 JSON。

## 单账号独立管理（ANYROUTER_ACCOUNT_* 前缀）

参考 [autocheck-anyrouter](https://github.com/rakuyoMo/autocheck-anyrouter) 方案，支持通过 `ANYROUTER_ACCOUNT_*` 前缀的环境变量独立管理每个账号。

### 用法

在 GitHub Environment Secrets 中添加以 `ANYROUTER_ACCOUNT_` 为前缀的 secret，每个 secret 包含一个账号的 JSON 配置：

```
ANYROUTER_ACCOUNT_123456 = {"cookies": {"session": "new_session_value"}}
ANYROUTER_ACCOUNT_789012_AGENTROUTER = {"cookies": {"session": "another_session"}, "api_user": "789012", "provider": "agentrouter"}
```

### 合并规则

- 如果 `ANYROUTER_ACCOUNTS` 中存在 `api_user` 与 `ANYROUTER_ACCOUNT_*` 后缀匹配的账号，独立配置中的字段会**覆盖**主配置中的对应字段（适合仅更新 cookies）
- 如果没有匹配到，独立配置的账号会作为新账号追加
- 自动去重：相同 `api_user` 只保留第一个

### 适用场景

- 某个账号 cookie 过期时，只需更新对应的 `ANYROUTER_ACCOUNT_*` secret，无需修改整个 `ANYROUTER_ACCOUNTS`
- 搭配 Chrome 插件自动推送 cookie（见下文）

## 自定义 Provider 配置（可选）

默认情况下，`anyrouter`、`agentrouter` 已内置配置，无需额外设置。如果你需要使用其他服务商，可以通过环境变量 `PROVIDERS` 配置：

### 基础配置（仅域名）

大多数情况下，只需提供 `domain` 即可，其他路径会自动使用默认值：

```json
{
  "customrouter": {
    "domain": "https://custom.example.com"
  }
}
```

### 完整配置（自定义路径）

如果服务商使用了不同的 API 路径、请求头或需要 WAF 绕过，可以额外指定：

```json
{
  "customrouter": {
    "domain": "https://custom.example.com",
    "login_path": "/auth/login",
    "sign_in_path": "/api/checkin",
    "user_info_path": "/api/profile",
    "api_user_key": "New-Api-User",
    "bypass_method": "waf_cookies",
    "waf_cookie_names": ["acw_tc", "cdn_sec_tc", "acw_sc__v2"]
  }
}
```

**关于 `bypass_method`**：

- 不设置或设置为 `null`：直接使用用户提供的 cookies 进行请求（适合无 WAF 保护的网站）
- 设置为 `"waf_cookies"`：使用 Playwright 打开浏览器获取 WAF cookies 后再进行请求（适合有 WAF 保护的网站）

> 注：`anyrouter` 和 `agentrouter` 已内置默认配置，无需在 `PROVIDERS` 中配置

### 在 GitHub Actions 中配置

1. 进入你的仓库 Settings -> Environments -> production
2. 添加新的 secret：
   - Name: `PROVIDERS`
   - Value: 你的 provider 配置（JSON 格式）

**字段说明**：

- `domain` (必需)：服务商的域名
- `login_path` (可选)：登录页面路径，默认为 `/login`（仅在 `bypass_method` 为 `"waf_cookies"` 时使用）
- `sign_in_path` (可选)：签到 API 路径，默认为 `/api/user/sign_in`
- `user_info_path` (可选)：用户信息 API 路径，默认为 `/api/user/self`
- `api_user_key` (可选)：API 用户标识请求头名称，默认为 `new-api-user`
- `bypass_method` (可选)：WAF 绕过方法
  - `"waf_cookies"`：使用 Playwright 打开浏览器获取 WAF cookies 后再执行签到
  - 不设置或 `null`：直接使用用户 cookies 执行签到（适合无 WAF 保护的网站）
- `waf_cookie_names` (可选)：绕过 WAF 所需 cookie 的名称列表，`bypass_method` 为 `waf_cookies` 时必须设置

**配置示例**（完整）：

```json
{
  "customrouter": {
    "domain": "https://custom.example.com",
    "login_path": "/auth/login",
    "sign_in_path": "/api/checkin",
    "user_info_path": "/api/profile",
    "api_user_key": "x-user-id",
    "bypass_method": "waf_cookies"
  }
}
```

**内置配置说明**：

- `anyrouter`：
  - `bypass_method: "waf_cookies"`（需要先获取 WAF cookies，然后执行签到）
  - `sign_in_path: "/api/user/sign_in"`
- `agentrouter`：
  - `bypass_method: null`（直接使用用户 cookies 执行签到）
  - `sign_in_path: "/api/user/sign_in"`

**重要提示**：

- `PROVIDERS` 是可选的，不配置则使用内置的 `anyrouter` 和 `agentrouter`
- 自定义的 provider 配置会覆盖同名的默认配置

## 开启通知

脚本支持多种通知方式，可以通过配置以下环境变量开启，如果 `webhook` 有要求安全设置，例如钉钉，可以在新建机器人时选择自定义关键词，填写 `AnyRouter`。

### 邮箱通知(STMP)

- `EMAIL_USER`: 发件人邮箱地址/STMP 登录地址
- `EMAIL_PASS`: 发件人邮箱密码/授权码
- `EMAIL_SENDER`: 邮件显示的发件人地址(可选，默认: EMAIL_USER)
- `CUSTOM_SMTP_SERVER`: 自定义发件人 SMTP 服务器(可选)
- `EMAIL_TO`: 收件人邮箱地址

### 钉钉机器人

- `DINGDING_WEBHOOK`: 钉钉机器人的 Webhook 地址

### 飞书机器人

- `FEISHU_WEBHOOK`: 飞书机器人的 Webhook 地址

### 企业微信机器人

- `WEIXIN_WEBHOOK`: 企业微信机器人的 Webhook 地址

### PushPlus 推送

- `PUSHPLUS_TOKEN`: PushPlus 的 Token

### Server 酱

- `SERVERPUSHKEY`: Server 酱的 SendKey

### Telegram Bot

- `TELEGRAM_BOT_TOKEN`: Telegram Bot 的 Token
- `TELEGRAM_CHAT_ID`: Telegram Chat ID

### Gotify 推送

- `GOTIFY_URL`: Gotify 服务的 URL 地址（例如: https://your-gotify-server/message）
- `GOTIFY_TOKEN`: Gotify 应用的访问令牌
- `GOTIFY_PRIORITY`: Gotify 消息优先级 (1-10, 默认为 9)

### Bark 推送

- `BARK_KEY`: Bark 应用的 Key（APP 打开时即可看到）
- `BARK_SERVER`: 自建 Bark 服务器地址 (可选，默认: https://api.day.app)

配置步骤：

1. 在仓库的 Settings -> Environments -> production -> Environment secrets 中添加上述环境变量
2. 每个通知方式都是独立的，可以只配置你需要的推送方式
3. 如果某个通知方式配置不正确或未配置，脚本会自动跳过该通知方式

## 故障排除

如果签到失败，请检查：

1. 账号配置格式是否正确
2. cookies 是否过期
3. API User 是否正确
4. 网站是否更改了签到接口
5. 查看 Actions 运行日志获取详细错误信息

## 本地开发环境设置

如果你需要在本地测试或开发，请按照以下步骤设置：

```bash
# 安装所有依赖
uv sync --dev

# 安装 Playwright 浏览器
uv run playwright install chromium

# 创建 .env 文件并配置
# 支持单行或多行 JSON（自动处理换行与空格）
# 示例：
# ANYROUTER_ACCOUNTS=[{"name":"账号1","cookies":{"session":"xxx"},"api_user":"12345"}]
# PROVIDERS={"agentrouter":{"domain":"https://agentrouter.org"}}

# 运行签到脚本
uv run checkin.py
```

## 测试

```bash
uv sync --dev

# 安装 Playwright 浏览器
uv run playwright install chromium

# 运行测试
uv run pytest tests/

# 查看测试覆盖率
uv run pytest tests/ --cov=. --cov-report=html
```

## 贡献指南

欢迎贡献代码！在提交 Pull Request 之前，请阅读[贡献指南](CONTRIBUTING.md)。

### 代码质量

本项目使用以下工具确保代码质量：

- **Ruff**: 代码风格检查和格式化
- **MyPy**: 静态类型检查
- **Bandit**: 安全漏洞扫描
- **Pytest**: 自动化测试
- **pre-commit**: Git 提交前自动检查

所有 Pull Request 会自动运行以下检查：

- ✅ 代码风格检查（Ruff Lint & Format）
- ✅ 类型检查（MyPy）
- ✅ 安全扫描（Bandit）
- ✅ 测试运行（Pytest）
- ✅ 测试覆盖率报告（Codecov）

### 本地开发

```bash
# 安装开发依赖
uv sync --dev

# 安装 pre-commit 钩子
uv run pre-commit install

# 运行代码检查
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run bandit -r . -c pyproject.toml

# 运行测试
uv run pytest tests/ --cov=.
```

## Chrome 扩展：AnyRouter Cookie Updater

本项目包含一个 Chrome 扩展 `AnyRouter Cookie Updater/`，可以自动从浏览器中提取已登录站点的 session cookie，并通过 GitHub API 推送到 GitHub Actions Environment Secrets。

### 工作原理

1. 从浏览器中提取已登录的 AnyRouter/其它平台的 `session` cookie
2. 使用 GitHub API + libsodium sealed box 加密后推送到 Environment Secrets
3. 生成 `ANYROUTER_ACCOUNT_*` 格式的 secret，签到脚本自动读取最新 cookie

### 安装步骤

1. 打开 Chrome，进入 `chrome://extensions/`
2. 开启右上角的 "开发者模式"
3. 点击 "加载已解压的扩展程序"
4. 选择本仓库中的 `AnyRouter Cookie Updater/` 目录

### 配置

打开扩展弹窗，填写以下配置：

| 配置项 | 说明 |
| --- | --- |
| **GitHub PAT** | Personal Access Token，需要 `repo` 权限（或 Environment secrets 写入权限） |
| **仓库 Owner** | GitHub 用户名 |
| **仓库名称** | 如 `anyrouter-check-in` |
| **Environment 名称** | 如 `production`（留空则推送到 repository secrets） |
| **账号列表** | JSON 数组，配置需要同步的账号 |
| **同步间隔** | 定时同步间隔（分钟），建议 360（6 小时） |

### 账号列表配置示例

```json
[
  {
    "domain": "https://anyrouter.top",
    "api_user": "123456",
    "env_key_suffix": "123456"
  },
  {
    "domain": "https://agentrouter.org",
    "api_user": "789012",
    "env_key_suffix": "789012_AGENTROUTER",
    "cookie_name": "session"
  }
]
```

**字段说明**：

- `domain`（必需）：站点域名，用于从浏览器中提取 cookie
- `api_user`（可选）：API 用户 ID，会写入 secret JSON 中
- `env_key_suffix`（推荐）：secret 名称后缀，生成 `ANYROUTER_ACCOUNT_{suffix}`
- `cookie_name`（可选）：要提取的 cookie 名称，默认为 `session`

### 前提条件

- 需要在浏览器中保持各站点的登录状态
- GitHub PAT 需要有对应仓库 Environment secrets 的写入权限

### 创建 GitHub PAT

1. 访问 [GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. 点击 "Generate new token"
3. 选择对应仓库，权限中启用 **Secrets** 的 Read and Write 权限
4. 生成后复制 token 到扩展配置中

## 免责声明

本脚本仅用于学习和研究目的，使用前请确保遵守相关网站的使用条款.

## 开发日志

### 2026-03-11

- **通知增强**：飞书/通知消息中每个账号现在显示所属平台名称和域名（如 `🌐 平台: freestyle (https://api.freestyle.cc.cd)`），解决了之前通知中不知道 Account 1 对应哪个网站的问题
- **多行 JSON 支持**：`ANYROUTER_ACCOUNTS` 和 `PROVIDERS` 环境变量支持多行 JSON，无需手动将在线配置生成器的输出压缩为一行
- **ANYROUTER_ACCOUNT_* 独立账号管理**：参考 [autocheck-anyrouter](https://github.com/rakuyoMo/autocheck-anyrouter) 方案，支持通过 `ANYROUTER_ACCOUNT_` 前缀的环境变量独立管理每个账号的 cookie，某个账号过期时只需更新对应 secret
- **GitHub Actions 适配**：workflow 自动注入所有 `ANYROUTER_ACCOUNT_*` secrets 到环境变量
- **Chrome 扩展 AnyRouter Cookie Updater**：参考 Flow2API Token Updater，构建了自动从浏览器提取 session cookie 并推送到 GitHub Actions Environment Secrets 的 Chrome 扩展，实现 cookie 失效后的自动更新
