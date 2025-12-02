# GitHub Actions 自动签到配置指南

本指南将帮你在 GitHub 上配置自动定时执行签到任务。

---

## 📋 配置步骤

### **第 1 步：Fork 仓库**

如果还没有 Fork，请：
1. 访问原仓库
2. 点击右上角的 **Fork** 按钮
3. 选择你的账号

---

### **第 2 步：创建 Environment**

1. 进入你 Fork 的仓库
2. 点击 **Settings**（设置）
3. 在左侧菜单找到 **Environments**
4. 点击 **New environment**
5. 输入环境名称：`production`
6. 点击 **Configure environment**

---

### **第 3 步：添加必需的 Secret**

在 `production` 环境中，点击 **Add environment secret**，添加以下配置：

#### ✅ **必需配置**

| Secret Name | Value 示例 | 说明 |
|------------|-----------|------|
| `ANYROUTER_ACCOUNTS` | `[{"name":"测试账号","cookies":{"session":"你的session"},"api_user":"12345"}]` | 账号配置（JSON 单行格式） |

**重要提示：**
- ⚠️ JSON 必须是**单行格式**，不能有换行
- ⚠️ 必须是**数组格式** `[...]`
- ⚠️ 所有双引号必须是英文引号 `"`

**单账号配置：**
```json
[{"name":"我的账号","cookies":{"session":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."},"api_user":"12345"}]
```

**多账号配置：**
```json
[{"name":"AnyRouter主账号","provider":"anyrouter","cookies":{"session":"session1"},"api_user":"12345"},{"name":"AgentRouter备用","provider":"agentrouter","cookies":{"session":"session2"},"api_user":"67890"}]
```

---

#### 📱 **可选：通知配置**

根据需要添加以下任意通知方式的 Secret：

##### 钉钉机器人
| Secret Name | Value 示例 |
|------------|-----------|
| `DINGDING_WEBHOOK` | `https://oapi.dingtalk.com/robot/send?access_token=xxx` |

##### 飞书机器人
| Secret Name | Value 示例 |
|------------|-----------|
| `FEISHU_WEBHOOK` | `https://open.feishu.cn/open-apis/bot/v2/hook/xxx` |

##### 企业微信机器人
| Secret Name | Value 示例 |
|------------|-----------|
| `WEIXIN_WEBHOOK` | `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` |

##### 邮箱通知
| Secret Name | Value 示例 |
|------------|-----------|
| `EMAIL_USER` | `your_email@gmail.com` |
| `EMAIL_PASS` | `your_app_password` |
| `EMAIL_TO` | `recipient@example.com` |
| `CUSTOM_SMTP_SERVER` | `smtp.gmail.com`（可选） |

##### PushPlus
| Secret Name | Value 示例 |
|------------|-----------|
| `PUSHPLUS_TOKEN` | `your_pushplus_token` |

##### Server酱
| Secret Name | Value 示例 |
|------------|-----------|
| `SERVERPUSHKEY` | `your_server_pushkey` |

##### Telegram Bot
| Secret Name | Value 示例 |
|------------|-----------|
| `TELEGRAM_BOT_TOKEN` | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `TELEGRAM_CHAT_ID` | `987654321` |

##### Gotify
| Secret Name | Value 示例 |
|------------|-----------|
| `GOTIFY_URL` | `https://your-gotify-server/message` |
| `GOTIFY_TOKEN` | `your_gotify_token` |
| `GOTIFY_PRIORITY` | `9` |

---

#### 🔧 **可选：自定义 Provider**

如果需要使用其他 NewAPI/OneAPI 平台：

| Secret Name | Value 示例 |
|------------|-----------|
| `PROVIDERS` | `{"customrouter":{"domain":"https://custom.example.com","bypass_method":"waf_cookies"}}` |

**完整配置示例（单行格式）：**
```json
{"customrouter":{"domain":"https://custom.example.com","login_path":"/login","sign_in_path":"/api/user/sign_in","user_info_path":"/api/user/self","api_user_key":"new-api-user","bypass_method":"waf_cookies"}}
```

---

### **第 4 步：启用 GitHub Actions**

1. 在仓库中点击 **Actions** 标签
2. 如果提示启用 Actions，点击 **I understand my workflows, go ahead and enable them**
3. 找到 **AnyRouter 自动签到** workflow
4. 如果显示禁用，点击 **Enable workflow**

---

### **第 5 步：手动测试运行**

1. 在 **Actions** 页面
2. 点击左侧的 **AnyRouter 自动签到**
3. 点击右侧的 **Run workflow** 下拉按钮
4. 选择分支（通常是 `main` 或 `master`）
5. 点击绿色的 **Run workflow** 按钮
6. 等待几秒钟，刷新页面查看运行状态

---

### **第 6 步：查看运行日志**

1. 点击刚才触发的 workflow 运行记录
2. 点击 **checkin** job
3. 展开各个步骤查看详细日志

**成功标志：**
```
[SUCCESS] 测试账号: Check-in successful!
[SUCCESS] All accounts check-in successful!
```

---

## ⏰ 自动执行时间

根据 `.github/workflows/checkin.yml` 配置：

```yaml
schedule:
  - cron: '0 */6 * * *'
```

- **执行频率**：每 6 小时一次
- **执行时间**（UTC）：00:00, 06:00, 12:00, 18:00
- **执行时间**（北京时间）：08:00, 14:00, 20:00, 02:00

**注意事项：**
- ⚠️ GitHub Actions 的定时任务可能会延迟 1-1.5 小时
- ⚠️ 如果仓库长期无活动，定时任务可能会被暂停
- ✅ 建议每周手动触发一次以保持活跃

---

## 🔧 修改执行时间

如果想修改执行频率，编辑 `.github/workflows/checkin.yml`：

### 每天执行一次（中国时间早上 8 点）
```yaml
schedule:
  - cron: '0 0 * * *'  # UTC 00:00 = 北京时间 08:00
```

### 每 12 小时执行一次
```yaml
schedule:
  - cron: '0 */12 * * *'
```

### 每天特定时间执行（如早上 8 点和晚上 8 点）
```yaml
schedule:
  - cron: '0 0,12 * * *'  # UTC 00:00 和 12:00
```

### Cron 表达式说明
```
┌───────────── 分钟 (0 - 59)
│ ┌───────────── 小时 (0 - 23)
│ │ ┌───────────── 日期 (1 - 31)
│ │ │ ┌───────────── 月份 (1 - 12)
│ │ │ │ ┌───────────── 星期 (0 - 6) (周日=0)
│ │ │ │ │
* * * * *
```

---

## 📊 监控运行状态

### 查看最近运行记录
1. 进入 **Actions** 页面
2. 查看 **AnyRouter 自动签到** 的运行历史
3. 绿色 ✅ 表示成功，红色 ❌ 表示失败

### 查看余额变化
在运行日志中搜索：
```
[BALANCE] 测试账号
💰 Current balance: $357.54, Used: $1145.15
```

---

## ⚠️ 常见问题

### 问题 1：Secrets 配置不生效
**解决方法：**
1. 检查 Secret 名称是否完全正确（区分大小写）
2. 确认 Secret 添加到了 `production` 环境，而不是仓库级别
3. 重新运行 workflow

### 问题 2：定时任务没有执行
**可能原因：**
- GitHub Actions 延迟（正常现象）
- 仓库长期无活动被暂停
- workflow 文件格式错误

**解决方法：**
- 手动触发一次 workflow
- 检查仓库 Actions 是否被禁用
- 验证 `.github/workflows/checkin.yml` 格式

### 问题 3：401 错误
**原因：** Session 过期（通常 1 个月）
**解决方法：**
1. 重新获取 session 值
2. 更新 `ANYROUTER_ACCOUNTS` Secret

### 问题 4：通知没有收到
**检查清单：**
- [ ] 对应的 Secret 是否已配置
- [ ] Secret 值是否正确
- [ ] 查看运行日志确认通知是否发送成功

---

## 📋 配置检查清单

完成配置后，请确认：

- [ ] 已创建 `production` 环境
- [ ] 已添加 `ANYROUTER_ACCOUNTS` Secret
- [ ] JSON 格式正确（单行，数组格式）
- [ ] 已启用 GitHub Actions
- [ ] 手动测试运行成功
- [ ] 查看日志确认签到成功
- [ ] （可选）已配置通知方式

---

## 🎯 下一步

配置完成后：
1. ✅ 等待定时任务自动执行
2. 📊 定期检查 Actions 运行记录
3. 💰 关注余额变化
4. 🔄 每月更新一次 Session（如果过期）

---

## 📞 获取帮助

如果遇到问题：
1. 查看 Actions 运行日志
2. 检查本指南的常见问题部分
3. 提交 GitHub Issue

---

祝签到愉快！🎉
