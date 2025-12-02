# 项目文件结构说明

## 📁 核心文件

```
anyrouter-check-in/
├── checkin.py                    # 主程序：自动签到脚本
├── pyproject.toml                # 项目配置和依赖管理
├── uv.lock                       # 依赖锁定文件
├── LICENSE                       # 开源协议
└── README.md                     # 项目说明文档
```

## 🔧 配置文件

```
├── .env                          # 🔒 环境变量配置（敏感信息，不会被提交）
├── .env.example                  # 环境变量配置模板
├── .gitignore                    # Git 忽略规则
├── .python-version               # Python 版本
└── .pre-commit-config.yaml       # Pre-commit 配置
```

## 📚 文档目录

```
├── docs/                         # 📖 所有文档集中存放
│   ├── QUICK_START.md            # 快速开始指南（5分钟配置）
│   ├── GITHUB_ACTIONS_GUIDE.md   # GitHub Actions 详细配置指南
│   ├── EMAIL_NOTIFICATION_GUIDE.md  # 邮件通知配置指南 ⭐
│   ├── TEST_GUIDE.md             # 本地测试指南
│   ├── PROJECT_STRUCTURE.md      # 项目结构说明（本文档）
│   ├── SECURITY_CHECKLIST.md     # 安全检查清单
│   └── COMPLETION_REPORT.md      # 项目完成报告
```

## 🛠️ 脚本目录

```
├── scripts/                      # 🔧 工具脚本集中存放
│   ├── test-local.ps1            # 本地测试自动化脚本
│   └── cleanup.ps1               # 清理临时文件脚本
```

## 📦 源代码

```
├── utils/                        # 工具模块目录
│   ├── config.py                 # 配置管理
│   └── notify.py                 # 通知功能（邮件、钉钉、飞书等）
└── tests/                        # 单元测试
    └── test_notify.py            # 通知模块测试
```

## 🎬 GitHub Actions

```
└── .github/
    └── workflows/
        └── checkin.yml           # 自动签到 workflow
```

## 📸 资源文件

```
└── assets/                       # 文档图片资源
    ├── check-in.png
    ├── request-api-user.png
    └── request-session.png
```

## 🔒 敏感文件（不会被提交到 Git）

以下文件包含敏感信息，已通过 `.gitignore` 排除：

```
.env                              # 包含账号信息、密码等
balance_hash.txt                  # 余额缓存
test_email.py                     # 测试脚本
.venv/                            # Python 虚拟环境
__pycache__/                      # Python 缓存
.pytest_cache/                    # 测试缓存
.ruff_cache/                      # Linter 缓存
```

## ⚠️ 重要提示

### 不会被提交的文件（安全）：
- ✅ `.env` - 环境变量配置（账号、密码）
- ✅ `balance_hash.txt` - 余额缓存
- ✅ `test_email.py` - 测试脚本
- ✅ `.venv/` - 虚拟环境
- ✅ 所有 `__pycache__/` 目录

### 会被提交的文件：
- ✅ `.env.example` - 配置模板（不包含敏感信息）
- ✅ 所有 `.md` 文档文件
- ✅ 所有 `.py` 源代码（除了 test_email.py）
- ✅ `.ps1` 脚本文件

## 🧹 清理命令

清理所有临时文件：
```powershell
.\cleanup.ps1
```

查看哪些文件会被 Git 忽略：
```powershell
git check-ignore -v .env balance_hash.txt test_email.py
```

查看当前 Git 状态：
```powershell
git status
```

## 📋 文件用途速查

| 文件 | 用途 | 是否提交 |
|------|------|---------|
| `.env` | 存储敏感配置 | ❌ 不提交 |
| `.env.example` | 配置模板 | ✅ 提交 |
| `checkin.py` | 签到主程序 | ✅ 提交 |
| `test_email.py` | 邮件测试 | ❌ 不提交 |
| `test-local.ps1` | 本地测试 | ✅ 提交 |
| `cleanup.ps1` | 清理脚本 | ✅ 提交 |
| `balance_hash.txt` | 余额缓存 | ❌ 不提交 |
| `GITHUB_ACTIONS_GUIDE.md` | GitHub 配置指南 | ✅ 提交 |
| `QUICK_START.md` | 快速开始 | ✅ 提交 |
| `TEST_GUIDE.md` | 测试指南 | ✅ 提交 |
