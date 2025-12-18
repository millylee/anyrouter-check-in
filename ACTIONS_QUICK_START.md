# 🚀 GitHub Actions 快速开始

本指南帮助你在 **5分钟内** 设置 GitHub Actions 自动签到。

---

## ⚡ 超快速设置（3步）

### 1️⃣ Fork & Clone
```bash
# 在 GitHub 上点击 Fork
git clone https://github.com/YOUR_USERNAME/anyrouter-check-in.git
cd anyrouter-check-in
```

### 2️⃣ 准备配置
```bash
# 复制模板
cp config.example.json config.json

# 编辑 config.json，填入你的 session cookies
# (获取方式见下方)
```

### 3️⃣ 推送到 GitHub
```bash
git add config.json
git commit -m "Add personal config"
git push
```

### 4️⃣ 设置 Secrets
在 GitHub 仓库设置中添加 `ANYROUTER_ACCOUNTS` Secret，值为：
```bash
# 在项目目录下运行这个命令获取格式
cat config.json | jq -c '.'
# 然后复制结果粘贴到 Secret 中
```

---

## 📱 如何获取 Session Cookies

### AnyRouter (anyrouter.top)
1. 访问 https://anyrouter.top
2. 登录你的账号
3. 按 F12 打开开发者工具
4. 切换到 **Application** 标签
5. 左侧点击 **Cookies** → **https://anyrouter.top**
6. 找到 `session`，双击值并复制

### AgentRouter (agentrouter.org)
1. 访问 https://agentrouter.org
2. 登录你的账号
3. 按 F12 打开开发者工具
4. 切换到 **Application** 标签
5. 左侧点击 **Cookies** → **https://agentrouter.org**
6. 找到 `session`，双击值并复制

---

## 🔐 Secret 配置详解

### 必需配置
在 GitHub → Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 填写内容 | 示例 |
|------------|---------|------|
| `ANYROUTER_ACCOUNTS` | 账户配置 JSON (单行) | `[{"name":"主账号","provider":"anyrouter","cookies":{"session":"xxx"},"api_user":"100044"}]` |

### 可选通知配置（按需）
| Secret 名称 | 用途 |
|------------|------|
| `PUSHPLUS_TOKEN` | 微信推送 |
| `DINGTALK_WEBHOOK` | 钉钉机器人 |
| `SERVERPUSHKEY` | Server 酱推送 |
| `FEISHU_WEBHOOK` | 飞书机器人 |
| `WECHAT_WORK_KEY` | 企业微信 |

---

## 🧪 测试配置

### 方法 1: 手动触发 Action
1. 进入 GitHub 仓库的 **Actions** 标签
2. 点击 **🚀 AnyRouter 自动签到**
3. 点击 **Run workflow** 按钮
4. 选择 **true** -> 点击绿色按钮

### 方法 2: 本地测试（推荐先测）
```bash
# 设置环境变量
export ANYROUTER_ACCOUNTS=$(cat config.json | jq -c '.')

# 运行签到
python checkin.py

# 或使用 run.sh
./run.sh
```

### 检查结果
成功标志：
```
✅ AnyRouter 主账号: Check-in successful!
✅ AgentRouter 备用: Check-in completed automatically
```

---

## 🕒 定时时间说明

工作流配置：
```yaml
schedule:
  - cron: '0 1 * * *'  # 北京时间 9:00 (UTC 1:00)
  - cron: '0 2 * * *'  # 北京时间 10:00 (UTC 2:00)
```

如果想修改运行时间，编辑 `.github/workflows/checkin.yml`：
```yaml
# 例如改为每天 8:00 和 20:00
- cron: '0 0 * * *'  # UTC 0:00 = 北京 8:00
- cron: '0 12 * * *' # UTC 12:00 = 北京 20:00
```

---

## 📊 监控运行情况

### 查看运行历史
1. Actions → AnyRouter 自动签到
2. 查看最近的运行记录（绿色 ✅ 成功，红色 ❌ 失败）
3. 点击进入查看详细日志

### 查看余额变化
日志会显示：
```
[BALANCE] AnyRouter 主账号
:money: Current balance: $245.1, Used: $4.9

[BALANCE] AgentRouter 备用
:money: Current balance: $148.72, Used: $1.28
```

### 余额变化通知（首次+变动时）
如果设置通知，余额变化时会收到推送。

---

## 💰 GitHub Actions 免费额度

- **免费账户**: 2000 分钟/月
- **本项目**: 每次运行 ≈ 2-5 分钟
- **每日 2 次**: 每月 ≈ 120-300 分钟
- **剩余**: 每月还有 1700+ 分钟用于其他任务

**完全足够个人使用！**

---

## 🐛 常见问题

### Q: 工作流失败，提示 "No module named 'httpx'"
A: 依赖安装失败，重试工作流即可，或检查 workflow 文件

### Q: 提示 "Cookie expired" 或 "401 Unauthorized"
A: Session 过期，重新获取并更新 Secret

### Q: Playwright 安装很慢？
A: 第一次慢，后续会缓存（≈30秒）

### Q: 想立即测试而不是等定时？
A: 在 Actions 页面手动触发即可

### Q: 如何更新配置？
A: 修改本地 config.json，重新 push，或直接更新 Secret

---

## 🎯 完整配置示例

### config.json
```json
[{
  "name": "AnyRouter 主账号",
  "provider": "anyrouter",
  "cookies": {"session": "MTc2NTkzMzU4N3xFQVFM..."},
  "api_user": "100044"
}, {
  "name": "AgentRouter 备用",
  "provider": "agentrouter",
  "cookies": {"session": "MTc2NjA1MTYyMnxFQVFM..."},
  "api_user": "61017"
}]
```

### Actions Secret
```
ANYROUTER_ACCOUNTS=[{"name":"AnyRouter主账号","provider":"anyrouter","cookies":{"session":"MTc2NTkzMzU4N3xFQVFM..."},"api_user":"100044"},{"name":"AgentRouter备用","provider":"agentrouter","cookies":{"session":"MTc2NjA1MTYyMnxFQVFM..."},"api_user":"61017"}]
```

---

## ✅ 完成检查清单

- [ ] Fork 本仓库
- [ ] Clone 到本地
- [ ] 创建并编辑 config.json
- [ ] 测试运行（本地）
- [ ] 推送到 GitHub
- [ ] 设置 ANYROUTER_ACCOUNTS Secret
- [ ] 手动触发 Actions 测试
- [ ] 检查运行日志确认成功
- [ ] ✅ 大功告成，每天自动运行！

---

**遇到问题？** 查看 `GITHUB_SECRETS_SETUP.md` 或 Issues 页面。