# 🚀 GitHub Actions 快速配置（5分钟搞定）

## 第 1 步：创建 Environment（1分钟）

```
你的仓库 → Settings → Environments → New environment
```

输入名称：`production`，点击 **Configure environment**

---

## 第 2 步：添加账号配置（2分钟）

点击 **Add environment secret**

### 配置 1：账号信息（必需）

**Name:**
```
ANYROUTER_ACCOUNTS
```

**Value（单行格式，替换为你的真实信息）:**
```json
[{"name":"我的账号","cookies":{"session":"你的session值"},"api_user":"你的api_user"}]
```

**真实示例：**
```json
[{"name":"测试账号","cookies":{"session":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdef123456"},"api_user":"12345"}]
```

---

## 第 3 步：启用并测试（2分钟）

### 3.1 启用 Actions
```
你的仓库 → Actions → Enable Actions
```

### 3.2 手动运行测试
```
Actions → AnyRouter 自动签到 → Run workflow → Run workflow
```

### 3.3 查看运行结果
```
点击运行记录 → checkin job → 查看日志
```

**成功标志：**
```
✅ [SUCCESS] 测试账号: Check-in successful!
✅ [SUCCESS] All accounts check-in successful!
```

---

## ✅ 完成！

配置完成后：
- ⏰ **自动执行**：每 6 小时运行一次
- 🕐 **执行时间**（北京时间）：02:00, 08:00, 14:00, 20:00
- 📊 **查看记录**：Actions 页面查看历史运行

---

## 🔔 可选：添加通知

### Telegram（推荐）

**Secret 1:**
```
Name: TELEGRAM_BOT_TOKEN
Value: 你的机器人Token
```

**Secret 2:**
```
Name: TELEGRAM_CHAT_ID
Value: 你的ChatID
```

### 钉钉

```
Name: DINGDING_WEBHOOK
Value: https://oapi.dingtalk.com/robot/send?access_token=xxx
```

### 邮箱

```
Name: EMAIL_USER
Value: your_email@gmail.com

Name: EMAIL_PASS
Value: your_app_password

Name: EMAIL_TO
Value: recipient@example.com
```

---

## ⚠️ 重要提示

1. ✅ JSON 必须是**单行格式**
2. ✅ 必须添加到 **production 环境**，不是仓库 Secrets
3. ✅ Session 有效期约 1 个月，过期后需要更新
4. ✅ GitHub Actions 定时任务可能延迟 1-1.5 小时

---

## 📸 配置截图参考

### 1. 创建 Environment
```
Settings → Environments → New environment → 输入 "production"
```

### 2. 添加 Secret
```
production 环境 → Add environment secret → 填写配置
```

### 3. 运行测试
```
Actions → AnyRouter 自动签到 → Run workflow
```

---

**详细配置说明请查看：** `GITHUB_ACTIONS_GUIDE.md`
