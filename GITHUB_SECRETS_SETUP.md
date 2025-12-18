# 🔐 GitHub Secrets 配置指南

Active → Inactive

## 🔧 必需的 Secrets

### 1. 核心配置

| Secret 名称 | 说明 | 是否必需 | 示例值 |
|------------|------|----------|--------|
| `ANYROUTER_ACCOUNTS` | **账户配置 JSON** | ✅ 必须 | `[{"name":"AnyRouter主账号","provider":"anyrouter","cookies":{"session":"xxx"},"api_user":"100044"}]` |

### 2. 可选 - 通知配置

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `PUSHPLUS_TOKEN` | PushPlus 推送 | `你的令牌` |
| `SERVERPUSHKEY` | Server 酱 | `你的Key` |
| `DINGDING_WEBHOOK` | 钉钉机器人 | `https://oapi.dingtalk.com/robot/send?access_token=xxx` |
| `FEISHU_WEBHOOK` | 飞书机器人 | `https://open.feishu.cn/open-apis/bot/v2/hook/xxx` |
| `WECHAT_WORK_KEY` | 企业微信 | `你的Key` |
| `GOTIFY_URL` | Gotify URL | `https://gotify.example.com` |
| `GOTIFY_TOKEN` | Gotify Token | `A.xxx` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | `123456789` |

## 🚀 设置步骤

### 第一步：准备账户配置

根据你本地的 `config.json` 创建单行 JSON：

```bash
# 方法 1: 使用 jq (推荐)
cat config.json | jq -c '.'
# 输出: [{"name":"AnyRouter主账号","provider":"anyrouter","cookies":{"session":"xxx"},"api_user":"100044"}]

# 方法 2: 手动压缩
# 1. 打开 config.json
# 2. 删除所有换行和多余空格
# 3. 确保是单行格式
```

### 第二步：添加 Secrets

1. 进入 GitHub 仓库
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 依次添加：

#### 示例：添加 ANYROUTER_ACCOUNTS

```
Secret name: ANYROUTER_ACCOUNTS
Secret value: [{"name":"AnyRouter主账号","provider":"anyrouter","cookies":{"session":"MTc2NTkzMzU4N3xFQVFM..."},"api_user":"100044"},{"name":"AgentRouter备用","provider":"agentrouter","cookies":{"session":"MTc2NjA1MTYyMnxFQVFM..."},"api_user":"61017"}]
```

### 第三步：验证配置

配置完成后，在 GitHub Actions 页面手动触发工作流测试：

1. 进入 **Actions** 标签
2. 点击 **AnyRouter 自动签到**
3. 点击 **Run workflow**
4. 选择 **true** 然后点击绿色按钮

## 📋 配置示例

### 只有 AnyRouter
```json
[{"name":"AnyRouter主账号","provider":"anyrouter","cookies":{"session":"你的session"},"api_user":"100044"}]
```

### 双平台配置
```json
[{"name":"AnyRouter主账号","provider":"anyrouter","cookies":{"session":"你的session"},"api_user":"100044"},{"name":"AgentRouter备用","provider":"agentrouter","cookies":{"session":"你的session"},"api_user":"61017"}]
```

### 多账户 AnyRouter
```json
[{"name":"主账号","provider":"anyrouter","cookies":{"session":"session1"},"api_user":"100044"},{"name":"备用账号","provider":"anyrouter","cookies":{"session":"session2"},"api_user":"100045"}]
```

## 🔍 如何获取 Session

### AnyRouter
1. 访问 https://anyrouter.top
2. 登录
3. F12 → Application → Cookies → session
4. 复制值

### AgentRouter
1. 访问 https://agentrouter.org
2. 登录
3. F12 → Application → Cookies → session
4. 复制值

## 🚨 故障排除

### 问题 1: Secrets 未设置
**现象**: 工作流失败，显示 "未设置 ANYROUTER_ACCOUNTS"
**解决**: 按上述步骤添加 Secrets

### 问题 2: JSON 格式错误
**现象**: "Account configuration format is incorrect"
**解决**:
- 检查是否是单行
- 检查逗号、引号是否正确
- 使用在线 JSON 验证工具检查

### 问题 3: Cookie 过期
**现象**: 签到失败，返回 401
**解决**: 重新登录获取新的 session，更新 Secrets

### 问题 4: Playwright 安装失败
**现象**: "Could not install playwright"
**解决**: GitHub Actions 会自动重试，通常下一次会成功

## 📊 监控运行情况

### 查看历史运行
1. 进入 **Actions** 标签
2. 点击 **AnyRouter 自动签到**
3. 查看最近的运行记录
4. 点击具体运行查看详细日志

### 检查是否成功
查看日志中的这些输出：
```
✅ AnyRouter 主账号: Check-in successful! ($245.1)
✅ AgentRouter 备用: Check-in completed automatically ($148.72)
```

## 💡 性能优化

### 浏览器缓存
工作流会自动缓存 Playwright 浏览器，首次运行需要 ~3 分钟，后续运行只需 ~30 秒。

### 依赖缓存
Python 依赖也会缓存，大幅加速运行速度。

## 🕒 定时说明

- **北京时间 9:00** → GitHub Actions `0 1 * * *` (UTC 1:00)
- **北京时间 10:00** → GitHub Actions `0 2 * * *` (UTC 2:00)

如果需要修改时间，编辑 `.github/workflows/checkin.yml` 中的 cron 表达式。

## 💰 GitHub Actions 免费额度

- **免费账户**: 2000 分钟/月
- **本工作流执行时间**: ~2-5 分钟/次
- **每日两次运行**: 约 4-10 分钟/天
- **月度消耗**: ~120-300 分钟（远低于免费额度）

---

**配置完成后，你的两个账户将每天 9:00 和 10:00 自动签到！** ✅