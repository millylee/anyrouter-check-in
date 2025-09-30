# Any Router 多账号自动签到

推荐搭配使用[Auo](https://github.com/millylee/auo)，支持任意 Claude Code Token 切换的工具。

**维护开源不易，如果本项目帮助到了你，请帮忙点个 Star，谢谢!**

用于 Claude Code 中转站 Any Router 多账号每日签到，一次 $25，限时注册即送 100 美金，[点击这里注册](https://anyrouter.top/register?aff=gSsN)。业界良心，支持 Claude Code 百万上下文（使用 `/model sonnet[1m]` 开启），`gemini-2.5-pro` 模型。

## 功能特性

- ✅ 单个/多账号自动签到
- ✅ 多种机器人通知（可选）
- ✅ 绕过 WAF 限制
- ✅ 支持 Stencil 模板自定义通知内容

## 使用方法

### 1. Fork 本仓库

点击右上角的 "Fork" 按钮，将本仓库 fork 到你的账户。

### 2. 获取账号信息

对于每个需要签到的账号，你需要获取：
1. **Cookies**: 用于身份验证
2. **API User**: 用于请求头的 new-api-user 参数

#### 获取 Cookies：
1. 打开浏览器，访问 https://anyrouter.top/
2. 登录你的账户
3. 打开开发者工具 (F12)
4. 切换到 "Application" 或 "存储" 选项卡
5. 找到 "Cookies" 选项
6. 复制所有 cookies

#### 获取 API User：
通常在网站的用户设置或 API 设置中可以找到，每个账号都有唯一的标识。

### 3. 设置 GitHub Environment Secret

1. 在你 fork 的仓库中，点击 "Settings" 选项卡
2. 在左侧菜单中找到 "Environments" -> "New environment"
3. 新建一个名为 `production` 的环境
4. 点击新建的 `production` 环境进入环境配置页
5. 点击 "Add environment secret" 创建 secret：
   - Name: `ANYROUTER_ACCOUNTS`
   - Value: 你的多账号配置数据

### 4. 多账号配置格式

支持单个与多个账号配置，可选 `name` 字段用于自定义账号显示名称：

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
- `name` (可选)：自定义账号显示名称，用于通知和日志中标识账号

如果未提供 `name` 字段，会使用 `Account 1`、`Account 2` 等默认名称。

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

- 脚本每6小时执行一次（1. action 无法准确触发，基本延时 1~1.5h；2. 目前观测到 anyrouter 的签到是每 24h 而不是零点就可签到）
- 你也可以随时手动触发签到

## 注意事项

- 请确保每个账号的 cookies 和 API User 都是正确的
- 可以在 Actions 页面查看详细的运行日志
- 支持部分账号失败，只要有账号成功签到，整个任务就不会失败
- 报 401 错误，请重新获取 cookies，理论 1 个月失效，但有 Bug，详见 [#6](https://github.com/millylee/anyrouter-check-in/issues/6)
- 请求 200，但出现 Error 1040（08004）：Too many connections，官方数据库问题，目前已修复，但遇到几次了，详见 [#7](https://github.com/millylee/anyrouter-check-in/issues/7)

## 配置示例

假设你有两个账号需要签到：

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

## 开启通知

脚本支持多种通知方式，可以通过配置以下环境变量开启，如果 `webhook` 有要求安全设置，例如钉钉，可以在新建机器人时选择自定义关键词，填写 `AnyRouter`。

### 传统配置方式（向后兼容）

> 本配置方式有可能将在未来的某个版本中被彻底移除，请尽快升级至[新版本的配置方式](#新的配置方式(推荐))。

#### 邮箱通知
- `EMAIL_USER`: 发件人邮箱地址
- `EMAIL_PASS`: 发件人邮箱密码/授权码
- `CUSTOM_SMTP_SERVER`: 自定义发件人SMTP服务器(可选)
- `EMAIL_TO`: 收件人邮箱地址

#### 钉钉机器人
- `DINGDING_WEBHOOK`: 钉钉机器人的 Webhook 地址

#### 飞书机器人
- `FEISHU_WEBHOOK`: 飞书机器人的 Webhook 地址

#### 企业微信机器人
- `WEIXIN_WEBHOOK`: 企业微信机器人的 Webhook 地址

#### PushPlus 推送
- `PUSHPLUS_TOKEN`: PushPlus 的 Token

#### Server酱
- `SERVERPUSHKEY`: Server酱的 SendKey

### 新的配置方式（推荐）

**支持 Stencil 模板自定义通知内容**

新的配置方式支持：
- 自定义通知模板（使用 Stencil 模板语法）
- 平台特定设置（如飞书的卡片模式、颜色主题等）
- 向后兼容旧的配置方式

#### 邮箱通知
```bash
# JSON 配置（支持自定义模板）
EMAIL_NOTIF_CONFIG='{"user":"your_email@example.com","pass":"your_password","to":"recipient@example.com","template":"自定义模板内容"}'
```

#### 钉钉机器人
```bash
# 方式一：JSON 配置
DINGTALK_NOTIF_CONFIG='{"webhook":"https://oapi.dingtalk.com/robot/send?access_token=xxx","template":"自定义模板"}'

# 方式二：纯 Webhook URL
DINGTALK_NOTIF_CONFIG="https://oapi.dingtalk.com/robot/send?access_token=xxx"
```

#### 飞书机器人
```bash
# 方式一：JSON 配置（支持卡片模式和颜色主题，以及自定义模板）
FEISHU_NOTIF_CONFIG='{"webhook":"https://open.feishu.cn/open-apis/bot/v2/hook/xxx","platform_settings":{"use_card":true,"color_theme":"blue"},"template":"自定义模板"}'

# 方式二：纯 Webhook URL（使用默认模板）
FEISHU_NOTIF_CONFIG="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

#### 企业微信机器人
```bash
# 方式一：JSON 配置（支持 markdown 样式和自定义模板）
WECOM_NOTIF_CONFIG='{"webhook":"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx","platform_settings":{"markdown_style":"markdown"},"template":"自定义模板"}'

# 方式二：纯 Webhook URL（使用默认模板）
WECOM_NOTIF_CONFIG="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
```

**`markdown_style` 配置说明**：
- `"markdown"`：使用 markdown 格式（默认值）
- `"markdown_v2"`：使用 markdown_v2 格式
- `null` 或其他值：使用纯文本格式

#### PushPlus 推送
```bash
# 方式一：JSON 配置（支持自定义模板）
PUSHPLUS_NOTIF_CONFIG='{"token":"your_pushplus_token","template":"自定义模板"}'

# 方式二：纯 Token（使用默认模板）
PUSHPLUS_NOTIF_CONFIG="your_pushplus_token"
```

#### Server酱
```bash
# 方式一：JSON 配置（支持自定义模板）
SERVERPUSH_NOTIF_CONFIG='{"send_key":"your_server_pushkey","template":"自定义模板"}'

# 方式二：纯 SendKey（使用默认模板）
SERVERPUSH_NOTIF_CONFIG="your_server_pushkey"
```

### 模板语法说明

使用 Stencil 模板语法，支持以下变量：

#### 可用变量

**基础变量**：
- `timestamp`: 执行时间戳字符串（格式：`YYYY-MM-DD HH:MM:SS`）

**统计数据**：
- `stats`: 统计数据对象，包含以下属性：
  - `stats.success_count`: 成功签到的账号数量
  - `stats.failed_count`: 失败的账号数量
  - `stats.total_count`: 总账号数量

**账号列表**：
- `accounts`: 完整的账号列表数组（包含所有账号），每个账号对象包含以下属性：
  - `name`: 账号名称
  - `status`: 状态（ `"success"` 或 `"failed"`）
  - `quota`: 当前余额（仅成功时有值，类型为 float）
  - `used`: 已使用余额（仅成功时有值，类型为 float）
  - `error`: 错误信息（仅失败时有值，类型为 string）

**便利变量**：
- `success_accounts`: 成功的账号列表（已按状态过滤）
- `failed_accounts`: 失败的账号列表（已按状态过滤）
- `has_success`: 布尔值，是否有成功的账号
- `has_failed`: 布尔值，是否有失败的账号
- `all_success`: 布尔值，是否所有账号都成功
- `all_failed`: 布尔值，是否所有账号都失败
- `partial_success`: 布尔值，是否部分成功部分失败

#### 重要说明

**Stencil 模板引擎限制**：
- ❌ 不支持比较操作符（`==`、`!=`、`<`、`>` 等）
- ❌ 不支持在循环中使用 `{% if account.status == "success" %}` 来判断状态

#### 模板示例

**推荐写法**（使用分组列表）：
```
{% if timestamp %}[TIME] 执行时间: {{ timestamp }}\n\n{% endif %}{% if success_accounts %}[SUCCESS] 成功账号:
{% for account in success_accounts %}• {{ account.name }}
💰 余额: ${{ account.quota }}, 已用: ${{ account.used }}
{% endfor %}
{% endif %}{% if failed_accounts %}[FAIL] 失败账号:
{% for account in failed_accounts %}• {{ account.name }}
⚠️ {{ account.error }}
{% endfor %}
{% endif %}[STATS] 签到统计:
✅ 成功: {{ stats.success_count }}/{{ stats.total_count }}
❌ 失败: {{ stats.failed_count }}/{{ stats.total_count }}
```

**简单模板示例**：
```
{{ timestamp }} - 成功: {{ success_count }}个，失败: {{ failed_count }}个
```

**条件渲染示例**：
```
{% if has_success %}有成功的账号{% endif %}
{% if has_failed %}有失败的账号{% endif %}
```

### 配置优先级

配置按以下优先级加载：
1. 新环境变量配置（如 `EMAIL_NOTIF_CONFIG`）
2. 默认模板配置文件（`notif_config/*.json`）
3. 旧环境变量配置（如 `EMAIL_USER`、`EMAIL_PASS` 等）

## 配置步骤：
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
playwright install chromium

# 按 .env.example 创建 .env
uv run checkin.py
```

## 测试

项目包含完整的测试套件，分为单元测试和集成测试：

```bash
# 安装所有依赖
uv sync --dev

# 安装 Playwright 浏览器
playwright install chromium

# 运行所有测试
uv run pytest tests/

# 仅运行单元测试（快速）
uv run pytest tests/unit/

# 仅运行集成测试（需要真实接口）
uv run pytest tests/integration/

# 运行特定测试文件
uv run pytest tests/unit/test_template_rendering.py -v
```

**测试目录说明**：
- `tests/unit/` - 单元测试：配置解析、数据模型、发送功能、模板渲染
- `tests/integration/` - 集成测试：真实通知接口测试

## 免责声明

本脚本仅用于学习和研究目的，使用前请确保遵守相关网站的使用条款.
