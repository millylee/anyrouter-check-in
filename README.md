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

#### 追加账号用的备用 Secret

除了 `ANYROUTER_ACCOUNTS`，还可以用 `EXTRA_ACCOUNTS`、`EXTRA_ACCOUNTS_2`、`EXTRA_ACCOUNTS_3`…… 存放额外账号，格式完全一样。脚本会按编号顺序加载并合并成一份账号列表。

之所以分多个 Secret：GitHub Secret 写入后无法再读出，如果所有账号都挤在一个 Secret 里，之后想加一个新站点就得把整份 JSON 重新写一遍，
很容易把已有账号漏掉、覆盖没了。新站点单独占一个编号 Secret 就不会互相影响。

同名账号（`name` 相同）后加载的会覆盖先加载的，可以用这个特性单独更新某个账号的凭据，而不用动原来的 Secret。

### 4. 多账号配置格式

支持单个与多个账号配置，可选 `name` 和 `provider` 字段：

```json
[
  {
    "name": "我的主账号",
    "email": "account1@example.com",
    "password": "account1_password"
  },
  {
    "name": "备用账号",
    "provider": "agentrouter",
    "email": "account2@example.com",
    "password": "account2_password"
  }
]
```

**字段说明**：

- `email` + `password`：推荐的浏览器登录方式，登录成功后会自动获取 cookies 与用户标识
- `cookies`：兼容旧版的 session cookies 登录方式
- `access_token`：新版 NewAPI/Ark717 等站点使用的 Bearer token；可单独使用，不需要 cookies 或 `api_user`
- `refresh_token`：Bearer access token 过期后用于自动换取新 token；GuysCode、小白 Code 等站点建议同时配置
- `api_user`：session cookies 登录时用于请求头的 new-api-user 参数；邮箱密码登录可省略
- `provider` (可选)：指定使用的服务商，默认为 `anyrouter`
- `name` (可选)：自定义账号显示名称，用于通知和日志中标识账号

**默认值说明**：

- 如果未提供 `provider` 字段，默认使用 `anyrouter`（向后兼容）
- 如果未提供 `name` 字段，会使用 `Account 1`、`Account 2` 等默认名称
- `anyrouter`、`agentrouter` 与 `futureppo` 配置已内置，无需填写 Provider

如果使用 session cookies 登录，接下来获取 cookies 与 api_user 的值。

通过 F12 工具，切到 Application 面板，拿到 session 的值，最好重新登录下，该值 1 个月有效期，但有可能提前失效，失效后报 401 错误，到时请再重新获取。

![获取 cookies](./assets/request-session.png)

通过 F12 工具，切到 Network 面板，可以过滤下，只要 Fetch/XHR，找到带 `New-Api-User`，这个值正常是 5 位数，如果是负数或者个位数，正常是未登录。

![获取 api_user](./assets/request-api-user.png)

部分站点已切换到新版 Bearer token 认证（NewAPI v1.0.0-rc 起）。这类站点的 `/api/user/self`
**完全不认 session cookie**，只认 `Authorization: Bearer`，所以只配 cookies 一定是
`401 Unauthorized, invalid access token`。

这类站点**推荐配邮箱密码**，让脚本自己登录并从 localStorage 取 token：

```json
{
  "name": "小鸡毛-thy1117",
  "provider": "xiaojimao",
  "email": "your@email.com",
  "password": "your_password"
}
```

原因是 access_token 只有**分钟级**有效期，靠 HttpOnly 的 `new_api_refresh` cookie 轮换。
手工从 F12 → Application → Local Storage 的 `new-api:auth-session` 里复制出来的
`access_token`，通常在下一次定时任务跑之前就已经过期：

```json
{
  "name": "小鸡毛-thy1117",
  "provider": "xiaojimao",
  "access_token": "替换成最新 access_token"
}
```

脚本在认证失败时会自动 POST `/api/user/auth/refresh` 尝试轮换一次 token，因此如果你
复制的是完整 Cookie 请求头（其中含 `new_api_refresh`），也可以撑过 token 过期。但只有
邮箱密码方式能长期免维护。

不要把 token 发到聊天或提交到仓库，只更新 GitHub Actions 的 `ANYROUTER_ACCOUNTS` Secret。

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

- 脚本每天北京时间 03:07、09:07、15:07、21:07 各触发一次；GitHub Actions 的定时任务是尽力而为，可能延迟数小时甚至跳过，多跑几次用于提高命中率（重复签到会被判定为「今日已签到」，不会有副作用）
- 你也可以随时手动触发签到

## 注意事项

- 请确保每个账号的 cookies 和 API User 都是正确的
- 可以在 Actions 页面查看详细的运行日志
- 支持部分账号失败，只要有账号成功签到，整个任务就不会失败
- 报 401 错误，请先确认站点仍使用 session cookies；若返回 `invalid access token`，说明站点已是 Bearer-only，改配邮箱密码（见上文），手填 `access_token` 会很快过期。旧版 cookies 理论 1 个月失效，但有 Bug，详见 [#6](https://github.com/millylee/anyrouter-check-in/issues/6)
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

### FuturePPO 配置

FuturePPO 已内置，账号只需指定 `provider: "futureppo"`。该站只支持 GitHub / LinuxDO / Passkey 等第三方登录，没有邮箱密码表单，所以要用 session cookie：

```json
{
  "name": "FuturePPO-Dodo",
  "provider": "futureppo",
  "cookies": { "session": "浏览器里的 session cookie" },
  "api_user": "你的用户 id"
}
```

`session` 与 `api_user` 的取法：登录后打开开发者工具，`Application → Cookies` 里复制 `session` 的值，`api_user` 就是 `/api/user/self` 返回的 `data.id`。

更推荐用「系统访问令牌」：控制台 → 个人设置 → 安全设置 → 系统访问令牌，复制后填 `access_token`，比 session 稳定：

```json
{
  "name": "FuturePPO-Dodo",
  "provider": "futureppo",
  "access_token": "系统访问令牌",
  "api_user": "你的用户 id"
}
```

站点挂在 Cloudflare 后面，有两点需要注意：

- `cf_clearance` 由脚本内置的浏览器自动获取，**不需要**手动填。
- 该 provider 的请求由浏览器页面内的 `fetch` 发出（`request_in_page: true`），而不是 Python 侧的 httpx。在 GitHub Actions 这类机房 IP 上，Cloudflare 会连 TLS(JA3) 与 HTTP/2 指纹一起校验，httpx 走 OpenSSL 握手伪装不了，即便持有刚拿到的有效 `cf_clearance` 也一律返回 403；改由页面自己发请求，指纹与挑战通过时完全一致。同时保留 `http2: false`，用于本机直连等仍走 httpx 的场景。

请只把凭据保存到 GitHub Actions 的 Secret，不要提交到仓库。

### 小白 Code 外站签到

小白 Code 使用独立签到页 `https://token.dialoguedui.com/checkin/`，不是 NewAPI 的通用签到接口。内置 `xiaobai` Provider 会先读取签到状态，未签到时再提交签到；access token 失效后会使用 refresh token 自动刷新。

```json
{
  "name": "小白Code-112581647",
  "provider": "xiaobai",
  "access_token": "Application → Local Storage 中的 auth_token",
  "refresh_token": "Application → Local Storage 中的 refresh_token"
}
```

该站的账号密码登录带 Turnstile 校验，GitHub Actions 不使用账号密码登录。请把上述 JSON 保存到 production Environment Secret `EXTRA_ACCOUNTS_13`，不要把 token 提交到仓库。

### GoRouter

GoRouter（`https://gorouter.app`）是新版 NewAPI，只支持 GitHub OAuth 登录，签到接口 `POST /api/user/checkin` 带 Cloudflare Turnstile 校验。因为无法在 CI 里跑 OAuth，凭据用**个人访问令牌（access_token）**：

1. 浏览器登录 GoRouter，打开 <https://gorouter.app/console/personal>
2. 找到「访问令牌 / Access Token」，点「重新生成」并复制（旧令牌会立刻作废，一个账号只有一个令牌位）
3. 把三个账号的令牌写成一份 JSON，存到 production Environment Secret `EXTRA_ACCOUNTS_15`

```json
[
  { "name": "GoRouter-account-1", "provider": "gorouter", "access_token": "xxx" },
  { "name": "GoRouter-account-2", "provider": "gorouter", "access_token": "xxx" },
  { "name": "GoRouter-account-3", "provider": "gorouter", "access_token": "xxx" }
]
```

实现要点：

- **为什么用 access_token 而不是 cookie**：NewAPI 的登录态是 15 分钟的 JWT 加一个会轮换的 `new_api_refresh` cookie，重放超过 30 秒宽限期会触发防重放并吊销整个会话族，CI 里极易把凭据用死。access_token 是不过期、不绑定会话的凭据，`/api/user/self`、`/api/user/checkin` 都接受它。仍然支持填 `cookies.new_api_refresh` 作为备选（会用持久化浏览器 Profile 保存轮换后的值）。
- **Turnstile 由运行器自己解**：签到卡片的 widget 挂在 closed shadow root 里，且只在服务端回「Turnstile token 为空」后才弹出。脚本改为在页面里显式渲染同一个 sitekey 的 widget，用真实鼠标事件点勾选框拿到 token，再作为 `?turnstile=` 查询参数提交——服务端 siteverify 同样接受。
- **成功判据只看服务端**：Turnstile 中间件校验失败时也返回 HTTP 200，只把 `success` 置 false，所以脚本以 `GET /api/user/checkin` 返回的 `stats.checked_in_today` 为唯一成功标准，Turnstile 相关失败会换新 token 重试最多 3 次。

请只把凭据保存到 GitHub Actions 的 Secret，不要提交到仓库。

### JustWoker

JustWoker（`https://api.justwoker.icu`）与 GoRouter 同为新版 NewAPI，签到接口 `POST /api/user/checkin` 同样带 Cloudflare Turnstile 校验，走完全一致的实现（页内渲染 widget 拿 token → 作为 `?turnstile=` 查询参数提交 → 以 `stats.checked_in_today` 判定成功）。凭据同样用**个人访问令牌（access_token）**：

1. 浏览器登录，打开 <https://api.justwoker.icu/console/personal>
2. 复制「访问令牌 / Access Token」（如未生成过则点「重新生成」，旧令牌会立刻作废）
3. 把账号令牌写成一份 JSON，存到 production Environment Secret `EXTRA_ACCOUNTS_17`

```json
[
  { "name": "JustWoker-account-1", "provider": "justwoker", "access_token": "xxx" },
  { "name": "JustWoker-account-2", "provider": "justwoker", "access_token": "xxx" }
]
```

### TaBiToken

TaBiToken（`https://tabitoken.com`，站点名 TaBiAI）同为新版 NewAPI，签到接口与 Turnstile 处理和 GoRouter 完全一致（`/profile` 会 302，签到卡片挂在 `/console/personal`）。凭据用**个人访问令牌（access_token）**，把三个账号写成一份 JSON 存到 production Environment Secret `EXTRA_ACCOUNTS_18`：

```json
[
  { "name": "TaBiToken-account-1", "provider": "tabitoken", "access_token": "xxx" },
  { "name": "TaBiToken-account-2", "provider": "tabitoken", "access_token": "xxx" },
  { "name": "TaBiToken-account-3", "provider": "tabitoken", "access_token": "xxx" }
]
```

### Ark API（WindHub）

Ark API（`https://windhub.cc`）是挂在 Cloudflare 后面的新版 NewAPI，签到接口 `POST /api/user/checkin`，站点设置里 `turnstile_check` 为关闭，所以**不需要** Turnstile。凭据用**系统访问令牌（access_token）**加**用户 ID（api_user）**：

1. 浏览器登录后打开 <https://windhub.cc/console/personal>
2. 复制「系统访问令牌 / Access Token」（如未生成过则点「重新生成」，旧令牌会立刻作废）
3. `api_user` 就是 `/api/user/self` 返回的 `data.id`，也显示在个人设置页
4. 写成一份 JSON 存到 production Environment Secret `EXTRA_ACCOUNTS_22`

```json
[{ "name": "WindHub-thy1117", "provider": "windhub", "access_token": "xxx", "api_user": "28157" }]
```

说明：

- 该站的令牌校验要求 `Authorization: Bearer <token>` 与 `New-Api-User: <用户 ID>` 同时带上，缺少后者会返回 `Unauthorized, New-Api-User header not provided`，所以 `api_user` 是必填项。
- 虽然站点在 Cloudflare 后面，但 `/api` 下的接口不触发挑战，httpx 直连即可拿到 200，因此不用开代理、WAF cookie 或页内请求。
- 重复签到时接口返回 HTTP 200 + `{"success": false, "message": "今日已签到"}`，脚本的 `ALREADY_CHECKED_KEYWORDS` 已覆盖「今日已签到」，会判定为成功。

### 老魔公益站

老魔公益站（`https://api.2020111.xyz`）与 GoRouter/JustWoker/TaBiToken 同构：新版 NewAPI，签到接口 `POST /api/user/checkin` 带 Cloudflare Turnstile 校验（站点 `turnstile_check` 为开启，缺少 token 时服务端返回「Turnstile token 为空」），走完全一致的实现（页内渲染 widget 拿 token → 作为 `?turnstile=` 查询参数提交 → 以 `stats.checked_in_today` 判定成功）。凭据用**系统访问令牌（access_token）**加**用户 ID（api_user）**：

1. 浏览器登录后打开 <https://api.2020111.xyz/console/personal>
2. 复制「系统访问令牌 / Access Token」（如未生成过则点「重新生成」，旧令牌会立刻作废）
3. `api_user` 就是 `/api/user/self` 返回的 `data.id`
4. 写成一份 JSON 存到 production Environment Secret `EXTRA_ACCOUNTS_23`

```json
[{ "name": "老魔公益站-thy1117", "provider": "laomo", "access_token": "xxx", "api_user": "4703" }]
```

### 123NHH

123NHH（`https://api.123nhh.com`）是新版 NewAPI，签到接口为 `POST /api/user/checkin`。站点关闭了 Turnstile，因此直接使用**系统访问令牌（access_token）**加**用户 ID（api_user）**即可：

1. 浏览器登录后打开 <https://api.123nhh.com/profile>
2. 复制「系统访问令牌 / Access Token」
3. `api_user` 就是个人资料页显示的用户 ID，或 `/api/user/self` 返回的 `data.id`
4. 写成一份 JSON 存到 production Environment Secret `EXTRA_ACCOUNTS_25`

```json
[{ "name": "123NHH-thy1117", "provider": "nhh123", "access_token": "xxx", "api_user": "3813" }]
```

### SuperAPI

SuperAPI（`https://superapi.buzz`）是新版 NewAPI，签到接口为 `POST /api/user/checkin`。站点关闭了 Turnstile，直接使用**系统访问令牌（access_token）**加**用户 ID（api_user）**：

1. 浏览器登录后打开 <https://superapi.buzz/profile>
2. 复制「系统访问令牌 / Access Token」
3. `api_user` 就是个人资料页显示的用户 ID，或 `/api/user/self` 返回的 `data.id`
4. 写成一份 JSON 存到 production Environment Secret `EXTRA_ACCOUNTS_26`

```json
[{ "name": "SuperAPI-thy1117", "provider": "superapi", "access_token": "xxx", "api_user": "8831" }]
```

### Gemai（哈基米 API 站）

Gemai（<https://api.gemai.cc/profile>）使用 NewAPI，签到接口为 `POST /api/user/checkin`。站点关闭了 Turnstile，使用**系统访问令牌（access_token）**加**用户 ID（api_user）**即可，无需浏览器验证。

将账号 JSON 保存到 production Environment Secret `EXTRA_ACCOUNTS_34`；该槽位会追加账号，不会覆盖已有账号：

```json
[{ "name": "Gemai-account-1", "provider": "gemai", "access_token": "替换成系统访问令牌", "api_user": "替换成用户 ID" }]
```

令牌仅存入 GitHub Secret，不要写进仓库。账号沿用现有每天四次的定时任务，重复签到按成功处理。

## 自定义 Provider 配置（可选）

默认情况下，`anyrouter`、`agentrouter`、`futureppo`、`twinkle`、`42w`、`kapibala`、`nianhua`、`sheapi`、`aiaiai`、`guyscode`、`xiaobai`、`xiaojimao`、`gorouter`、`qingjiu`、`justwoker`、`tabitoken`、`windhub`、`laomo`、`nhh123`、`superapi`、`gemai` 已内置配置，无需额外设置。如果你需要使用其他服务商，可以通过环境变量 `PROVIDERS` 配置：

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
- 设置为 `"waf_cookies"`：使用 CloakBrowser 打开浏览器获取 WAF cookies 后再进行请求（适合有 WAF 保护的网站）

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
  - `"waf_cookies"`：使用 CloakBrowser 打开浏览器获取 WAF cookies 后再执行签到
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
  - `bypass_method: "waf_cookies"`（需要获取 `acw_tc`）
  - `sign_in_path: null`（查询用户信息时自动签到）
  - `use_proxy: true`

**重要提示**：

- `PROVIDERS` 是可选的，不配置则使用内置的 `anyrouter` 和 `agentrouter`
- 自定义的 provider 配置会覆盖同名的默认配置

## 代理配置（可选）

内置的 `agentrouter` 默认 `use_proxy: true`。如果你的运行环境访问该平台不稳定，可以在 GitHub Actions 中配置 mihomo 订阅代理。

在仓库 Settings -> Environments -> production -> Environment secrets 中添加：

- `PROXY_SUBSCRIPTION_URL`：Clash/Mihomo 订阅链接。设置后，workflow 会运行 `scripts/setup_mihomo_proxy.sh`，启动本地代理并写入 `CHECKIN_PROXY_URL`。

本地运行时也可以直接使用已有代理：

```bash
CHECKIN_PROXY_URL=http://127.0.0.1:7890
PROVIDERS={"agentrouter":{"use_proxy":true}}
```

如果使用订阅脚本，默认会用 `https://www.google.com/generate_204` 测试代理连通性；也可以通过 `PROXY_TEST_URL` 覆盖。

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

# 安装 CloakBrowser 浏览器
uv run python -m cloakbrowser install
# 如需使用本地浏览器，可设置 CLOAKBROWSER_BINARY_PATH=/path/to/browser

# 创建 .env 文件并配置（注意：JSON 必须是单行格式）
# 示例：
# ANYROUTER_ACCOUNTS=[{"name":"账号1","email":"your@email.com","password":"your_password"}]
# PROVIDERS={"agentrouter":{"domain":"https://agentrouter.org"}}
# PROXY_SUBSCRIPTION_URL=https://example.com/sub?token=xxx
# CHECKIN_PROXY_URL=http://127.0.0.1:7890

# 运行签到脚本
uv run checkin.py
```

## 测试

```bash
uv sync --dev

# 浏览器相关测试或本地登录可安装 CloakBrowser，或设置 CLOAKBROWSER_BINARY_PATH 指向本地浏览器
uv run python -m cloakbrowser install

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

## 免责声明

本脚本仅用于学习和研究目的，使用前请确保遵守相关网站的使用条款.
