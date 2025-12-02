# 本地测试指南

## 📝 准备工作

### 1. 编辑 `.env` 文件

将你的真实账号信息填入 `.env` 文件：

```bash
ANYROUTER_ACCOUNTS=[{"name":"我的账号","cookies":{"session":"你的真实session"},"api_user":"你的真实api_user"}]
```

**真实示例：**
```bash
ANYROUTER_ACCOUNTS=[{"name":"主账号","cookies":{"session":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."},"api_user":"12345"}]
```

### 2. 多账号配置示例

```bash
ANYROUTER_ACCOUNTS=[{"name":"账号1","cookies":{"session":"session1"},"api_user":"12345"},{"name":"账号2","provider":"agentrouter","cookies":{"session":"session2"},"api_user":"67890"}]
```

---

## 🚀 运行测试

### 方式 1：使用自动化脚本（推荐）

```powershell
.\scripts\test-local.ps1
```

这个脚本会自动：
- ✅ 检查 .env 配置
- ✅ 安装依赖
- ✅ 安装浏览器
- ✅ 运行签到

### 方式 2：手动运行

```powershell
# 1. 安装依赖（首次运行）
uv sync

# 2. 安装 Playwright 浏览器（首次运行）
uv run playwright install chromium

# 3. 运行签到脚本
uv run python checkin.py
```

### 方式 3：运行单元测试

```powershell
# 运行所有测试
uv run pytest tests/ -v

# 运行通知测试
uv run pytest tests/test_notify.py -v

# 运行测试并查看覆盖率
uv run pytest tests/ --cov=. --cov-report=html
```

---

## 📊 预期输出

成功时会看到类似输出：

```
[INFO] Loaded 1 custom provider(s) from PROVIDERS environment variable
[PROCESSING] 我的账号: Starting browser to get WAF cookies...
[PROCESSING] 我的账号: Access login page to get initial cookies...
[SUCCESS] 我的账号: Successfully checked in! Balance: $25.50 (Used: $10.20)
✅ Checked in successfully for 1 account(s)
```

失败时会看到：

```
[ERROR] 我的账号: Check-in failed: 401 Unauthorized
❌ All accounts failed to check in
```

---

## 🔍 常见问题

### 问题 1：401 错误
**原因：** Session 过期
**解决：** 重新获取 session 值

### 问题 2：找不到 new-api-user
**原因：** api_user 值不正确
**解决：** 重新从网络请求中获取正确的值

### 问题 3：浏览器无法启动
**原因：** Playwright 浏览器未安装
**解决：** 运行 `uv run playwright install chromium`

---

## 📋 测试检查清单

- [ ] 已创建并编辑 `.env` 文件
- [ ] 填入真实的 session 值
- [ ] 填入真实的 api_user 值
- [ ] 运行 `uv sync` 安装依赖
- [ ] 运行 `uv run playwright install chromium`
- [ ] 运行 `uv run python checkin.py` 测试

---

## 🎯 下一步

测试成功后：

1. 将配置添加到 GitHub Secrets
2. 在 Actions 中启用 workflow
3. 手动触发一次测试
4. 等待自动定时运行（每6小时）
