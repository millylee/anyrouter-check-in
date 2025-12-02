# 📧 如何在 GitHub Actions 中配置邮件通知

## 问题说明

本地的 `.env` 文件不会被提交到 GitHub（已被 `.gitignore` 忽略），那么 GitHub Actions 如何发送邮件通知呢？

**答案：使用 GitHub Environment Secrets**

---

## 🔑 配置步骤

### 第 1 步：进入仓库设置

```
你的仓库 → Settings → Environments → production
```

如果没有 `production` 环境，先创建它：
1. 点击 **New environment**
2. 输入名称：`production`
3. 点击 **Configure environment**

---

### 第 2 步：添加邮件配置 Secrets

在 `production` 环境中，点击 **Add environment secret**，添加以下配置：

#### 必需配置（账号信息）

| Secret Name | Value 示例 | 说明 |
|------------|-----------|------|
| `ANYROUTER_ACCOUNTS` | `[{"name":"测试账号","cookies":{"session":"你的session"},"api_user":"19188"}]` | 账号配置（JSON 单行格式） |

#### 可选配置（邮件通知）

| Secret Name | Value 示例 | 说明 |
|------------|-----------|------|
| `EMAIL_USER` | `your_email@qq.com` | 发件邮箱 |
| `EMAIL_PASS` | `your_authorization_code` | QQ 邮箱授权码 |
| `EMAIL_TO` | `recipient@example.com` | 收件邮箱 |
| `CUSTOM_SMTP_SERVER` | `smtp.qq.com` | SMTP 服务器 |

---

## 📝 详细说明

### QQ 邮箱授权码获取

1. 登录 QQ 邮箱网页版
2. 设置 → 账户 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务
3. 开启 **IMAP/SMTP服务**
4. 点击 **生成授权码**
5. 发送短信验证
6. 复制 16 位授权码（例如：`abcd1234efgh5678`）

### 其他邮箱服务商

#### Gmail
```
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=应用专用密码
CUSTOM_SMTP_SERVER=smtp.gmail.com
```

#### Outlook
```
EMAIL_USER=your_email@outlook.com
EMAIL_PASS=账号密码
CUSTOM_SMTP_SERVER=smtp-mail.outlook.com
```

#### 163 邮箱
```
EMAIL_USER=your_email@163.com
EMAIL_PASS=授权码
CUSTOM_SMTP_SERVER=smtp.163.com
```

---

## 🔄 配置同步说明

### 本地 vs GitHub

| 配置项 | 本地（.env） | GitHub Actions |
|-------|------------|----------------|
| **存储位置** | `.env` 文件 | Environment Secrets |
| **配置方式** | 直接编辑文件 | 在仓库 Settings 中添加 |
| **使用场景** | 本地测试 | 自动签到 |
| **是否同步** | ❌ 不会自动同步 | - |

**重要提示：**
- ⚠️ 本地 `.env` 和 GitHub Secrets 是**完全独立**的
- ⚠️ 修改本地 `.env` 后，需要**手动更新** GitHub Secrets
- ⚠️ GitHub Secrets 一旦保存**无法查看**，只能覆盖更新

---

## 🎯 配置示例

### 完整的 GitHub Secrets 配置

假设你的本地 `.env` 文件内容如下：

```bash
# 本地 .env 文件
ANYROUTER_ACCOUNTS=[{"name":"我的账号","cookies":{"session":"你的真实session值"},"api_user":"19188"}]
EMAIL_USER=your_email@qq.com
EMAIL_PASS=your_authorization_code
EMAIL_TO=recipient@example.com
CUSTOM_SMTP_SERVER=smtp.qq.com
```

那么在 GitHub Secrets 中需要添加：

#### Secret 1: ANYROUTER_ACCOUNTS
```
Name: ANYROUTER_ACCOUNTS
Value: [{"name":"我的账号","cookies":{"session":"你的真实session值"},"api_user":"19188"}]
```

#### Secret 2: EMAIL_USER
```
Name: EMAIL_USER
Value: your_email@qq.com
```

#### Secret 3: EMAIL_PASS
```
Name: EMAIL_PASS
Value: your_authorization_code
```

#### Secret 4: EMAIL_TO
```
Name: EMAIL_TO
Value: recipient@example.com
```

#### Secret 5: CUSTOM_SMTP_SERVER
```
Name: CUSTOM_SMTP_SERVER
Value: smtp.qq.com
```

---

## ✅ 验证配置

### 1. 检查 Secrets 是否配置正确

进入：`Settings → Environments → production`

应该看到以下 Secrets：
- ✅ ANYROUTER_ACCOUNTS
- ✅ EMAIL_USER
- ✅ EMAIL_PASS
- ✅ EMAIL_TO
- ✅ CUSTOM_SMTP_SERVER

### 2. 手动触发测试

1. 进入 **Actions** 页面
2. 选择 **AnyRouter 自动签到**
3. 点击 **Run workflow**
4. 查看运行日志

### 3. 检查邮件

如果配置正确：
- ✅ 签到成功会收到邮件通知（首次运行或余额变化）
- ✅ 签到失败也会收到邮件通知

如果没收到邮件：
1. 检查垃圾邮件文件夹
2. 查看 Actions 日志中的 `[Email]` 输出
3. 确认 Secrets 配置无误

---

## 🚨 常见问题

### Q1: 我不想配置邮件通知，可以吗？
**A:** 可以！邮件通知是**可选的**。只配置 `ANYROUTER_ACCOUNTS` 即可，签到仍然正常运行，只是不会发送通知。

### Q2: 如何更新 Session（过期后）？
**A:** 
1. 重新获取 session 值
2. 更新本地 `.env` 文件
3. 更新 GitHub Secrets 中的 `ANYROUTER_ACCOUNTS`

### Q3: GitHub Secrets 安全吗？
**A:** 
- ✅ 非常安全！GitHub Secrets 经过加密存储
- ✅ 在日志中自动隐藏（显示为 `***`）
- ✅ 只有仓库所有者和管理员可以管理

### Q4: 能在 Actions 日志中看到我的密码吗？
**A:** 
- ❌ 不能！GitHub 会自动将 Secrets 的值在日志中替换为 `***`
- ✅ 你的邮箱、密码、Session 都是安全的

---

## 📸 配置截图说明

### 1. 创建 Environment
![创建环境](https://docs.github.com/assets/cb-28038/images/help/actions/environments-create.png)

### 2. 添加 Secret
![添加Secret](https://docs.github.com/assets/cb-48957/images/help/actions/actions-environment-secret.png)

### 3. 运行 Workflow
![运行Workflow](https://docs.github.com/assets/cb-33899/images/help/actions/manual-workflow-run.png)

---

## 🎓 工作原理

### GitHub Actions Workflow 如何使用 Secrets

在 `.github/workflows/checkin.yml` 中：

```yaml
- name: 执行签到
  env:
    ANYROUTER_ACCOUNTS: ${{ secrets.ANYROUTER_ACCOUNTS }}
    EMAIL_USER: ${{ secrets.EMAIL_USER }}
    EMAIL_PASS: ${{ secrets.EMAIL_PASS }}
    EMAIL_TO: ${{ secrets.EMAIL_TO }}
    CUSTOM_SMTP_SERVER: ${{ secrets.CUSTOM_SMTP_SERVER }}
  run: |
    uv run checkin.py
```

**说明：**
1. `${{ secrets.SECRET_NAME }}` 语法从 Environment Secrets 读取值
2. 这些值会作为环境变量传递给 Python 脚本
3. Python 脚本通过 `os.getenv()` 读取这些环境变量
4. 与本地 `.env` 文件的工作方式完全相同

---

## 📋 快速配置清单

- [ ] 创建 `production` 环境
- [ ] 添加 `ANYROUTER_ACCOUNTS` Secret（必需）
- [ ] 添加 `EMAIL_USER` Secret（可选）
- [ ] 添加 `EMAIL_PASS` Secret（可选）
- [ ] 添加 `EMAIL_TO` Secret（可选）
- [ ] 添加 `CUSTOM_SMTP_SERVER` Secret（可选）
- [ ] 手动触发测试
- [ ] 查看运行日志
- [ ] 检查邮箱（如果配置了邮件通知）

---

**需要帮助？查看 [QUICK_START.md](QUICK_START.md) 获取更多信息。**
