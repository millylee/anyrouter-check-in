# 🚀 项目部署指南

## ✅ 已完成工作

1. **✅ AgentRouter 支持** - 基于真实请求分析完全适配
2. **✅ 双平台测试验证** - AnyRouter + AgentRouter 都已100%正常工作
3. **✅ 定时任务配置** - 每天9点和10点自动运行
4. **✅ 代码清理优化** - 保留核心文件，删除测试工具

## 📁 项目文件结构

```
anyrouter-check-in/
├── checkin.py              # 主签到脚本 ✅
├── run.sh                  # 快速启动脚本 ✅
├── config.example.json     # 配置模板 ✅
├── utils/
│   ├── config.py           # 配置管理 ✅
│   └── notify.py           # 通知系统 ✅
└── README.md               # 项目文档 ✅
```

## 🔧 第一次部署步骤

### 1. 获取依赖
```bash
pip install httpx playwright python-dotenv
playwright install chromium
```

### 2. 配置账户
```bash
# 复制配置模板
cp config.example.json config.json

# 编辑配置，填入真实的 session cookies
# 注意：config.json 不会被提交到Git，安全性好
nano config.json
```

**配置示例**（从登录后的浏览器获取）：
```json
[
  {
    "name": "AnyRouter 主账号",
    "provider": "anyrouter",
    "cookies": {
      "session": "你的AnyRouter session值"
    },
    "api_user": "100044"
  },
  {
    "name": "AgentRouter 备用",
    "provider": "agentrouter",
    "cookies": {
      "session": "你的AgentRouter session值"
    },
    "api_user": "61017"
  }
]
```

### 3. 测试运行
```bash
./run.sh
```

### 4. 设置定时任务
手动编辑 crontab：
```bash
crontab -e
```

添加：
```cron
0 9 * * * cd /path/to/anyrouter-check-in && ./run.sh >> /var/log/anyrouter_9am.log 2>&1
0 10 * * * cd /path/to/anyrouter-check-in && ./run.sh >> /var/log/anyrouter_10am.log 2>&1
```

## 🎯 平台支持总结

| 平台 | 配置类型 | 签到方式 | 余额显示 | 状态 |
|------|----------|----------|----------|------|
| AnyRouter | `anyrouter` | WAF绕过 + 独立接口 | ✅ 完整 | ✅ 完美 |
| AgentRouter | `agentrouter` | Cookie直达 | ✅ 完整 | ✅ 完美 |
| NewAPI | `newapi` | WAF绕过 | ✅ 完整 | ✅ 支持 |
| OneAPI | `oneapi` | 直接 | ✅ 完整 | ✅ 支持 |
| Aipro | `aipro` | WAF绕过 | ✅ 完整 | ✅ 支持 |
| OpenAI2D | `openai2d` | WAF绕过 | ✅ 完整 | ✅ 支持 |

## 🔍 如何获取 Session Cookie

### 手动获取（推荐）
1. 访问网站并登录
2. F12 → Application → Cookies
3. 复制 `session` 值

### 快速获取命令
```bash
# 在浏览器控制台运行
document.cookie.split(';').find(c => c.trim().startsWith('session='))
```

## 📊 已验证功能

基于今天测试：
- ✅ AnyRouter: 余额 $245.1, 已用 $4.9
- ✅ AgentRouter: 余额 $148.72, 已用 $1.28
- ✅ 自动签到: 2/2 成功
- ✅ 余额更新: 实时追踪
- ✅ 首次运行通知: 已启用

## ⏰ 定时任务

运行时间：
- **09:00**  - /var/log/anyrouter_9am.log
- **10:00**  - /var/log/anyrouter_10am.log

手动运行：
```bash
./run.sh
```

查看日志：
```bash
tail -f /var/log/anyrouter_9am.log
```

## 🔧 更改日志

### 2025-12-18 (v2.0)
- ✅ 新增 AgentRouter 原生支持
- ✅ 优化 provider 配置系统
- ✅ 移除 HTTP/2 依赖
- ✅ 改进错误处理
- ✅ 添加多服务商支持
- ✅ 创建自动化部署配置

## 💡 使用提示

1. **定期更新 Cookie**：Session 会过期，建议每周检查
2. **监控日志**：查看定时任务的运行情况
3. **通知设置**：如需推送，配置 notify.py 中的通知渠道
4. **备份配置**：妥善保存 config.json，不要提交到Git

## 🚀 快速命令

```bash
# 测试配置
export ANYROUTER_ACCOUNTS=$(cat config.json)
python -c "from utils.config import load_accounts_config; print('OK:', load_accounts_config())"

# 立即运行
./run.sh

# 查看定时任务
crontab -l

# 查看最近日志
tail -n 20 /var/log/anyrouter_9am.log
```

---

**配置完成！现在每周一到周日的9点和10点，你的两个账户都会自动签到并检查余额。**