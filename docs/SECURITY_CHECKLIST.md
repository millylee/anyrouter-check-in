# 🔒 隐私和安全检查清单

## ✅ 文件整理完成

### 已忽略的敏感文件（不会被提交）

- ✅ `.env` - 环境变量配置（包含账号、密码、授权码）
- ✅ `balance_hash.txt` - 余额缓存
- ✅ `test_email.py` - 测试脚本
- ✅ `.venv/` - Python 虚拟环境
- ✅ `__pycache__/` - Python 缓存目录
- ✅ `.pytest_cache/` - 测试缓存
- ✅ `.ruff_cache/` - Linter 缓存

### 安全的文件（可以提交）

- ✅ `.env.example` - 配置模板（不包含真实信息）
- ✅ 所有文档文件（.md）
- ✅ 源代码文件（.py）
- ✅ 脚本文件（.ps1）
- ✅ GitHub Actions 配置

---

## 🔍 安全验证命令

### 1. 检查 .env 是否被忽略
```powershell
git check-ignore -v .env
# 期望输出：.gitignore:15:.env    .env
```

### 2. 验证敏感文件不在 Git 追踪中
```powershell
git ls-files | Select-String ".env$|balance_hash|test_email"
# 期望输出：无结果（说明这些文件未被追踪）
```

### 3. 查看将要提交的文件
```powershell
git status
# 确保不包含 .env、balance_hash.txt 等敏感文件
```

### 4. 查看所有未追踪的文件
```powershell
git status --ignored
# 查看被忽略的文件列表
```

---

## 📝 .env 文件内容说明

### 敏感信息（绝不能提交）

```bash
# ❌ 以下内容包含敏感信息，仅存在于 .env 文件中

# 账号配置 - 包含 session 和 api_user
ANYROUTER_ACCOUNTS=[{"name":"测试账号","cookies":{"session":"真实的session值"},"api_user":"19188"}]

# 邮箱配置 - 包含真实邮箱和授权码
EMAIL_USER=your_email@qq.com
EMAIL_PASS=your_authorization_code           # QQ 邮箱授权码
EMAIL_TO=recipient@example.com
CUSTOM_SMTP_SERVER=smtp.qq.com
```

### 公开模板（可以提交）

```bash
# ✅ .env.example 文件内容（不含真实信息）

ANYROUTER_ACCOUNTS=[{"cookies":{"session":"你的session值"},"api_user":"你的api_user值"}]

# 可选：通知配置
# EMAIL_USER=your_email@example.com
# EMAIL_PASS=your_password
# EMAIL_TO=recipient@example.com
```

---

## ⚠️ GitHub 配置说明

### 本地配置 vs GitHub 配置

| 项目 | 本地配置（.env） | GitHub 配置 |
|-----|----------------|------------|
| **存储位置** | `.env` 文件 | Environment Secrets |
| **是否提交** | ❌ 不提交 | - |
| **配置方式** | 直接编辑文件 | Settings → Environments → production |
| **使用场景** | 本地测试 | GitHub Actions 自动运行 |

### GitHub Secrets 配置步骤

1. **进入仓库设置**
   ```
   你的仓库 → Settings → Environments → production
   ```

2. **添加 Secret（从 .env 复制值）**
   
   | Secret Name | 从 .env 复制 |
   |------------|-------------|
   | `ANYROUTER_ACCOUNTS` | `ANYROUTER_ACCOUNTS` 的值 |
   | `EMAIL_USER` | `EMAIL_USER` 的值 |
   | `EMAIL_PASS` | `EMAIL_PASS` 的值 |
   | `EMAIL_TO` | `EMAIL_TO` 的值 |
   | `CUSTOM_SMTP_SERVER` | `CUSTOM_SMTP_SERVER` 的值 |

3. **注意事项**
   - ⚠️ GitHub Secrets 和本地 `.env` 是独立的
   - ⚠️ 修改本地 `.env` 后，需要同步更新 GitHub Secrets
   - ⚠️ GitHub Secrets 一旦保存无法查看，只能覆盖更新

---

## 🛡️ 提交前检查清单

在执行 `git add` 和 `git commit` 之前，请确认：

- [ ] `.env` 文件不在 `git status` 的列表中
- [ ] `balance_hash.txt` 不在提交列表中
- [ ] `test_email.py` 不在提交列表中
- [ ] 执行 `git check-ignore -v .env` 返回正确的忽略规则
- [ ] 查看 `git diff` 确保没有敏感信息
- [ ] `.gitignore` 文件已更新并包含所有敏感文件

---

## 🚨 如果不小心提交了敏感信息

### 立即采取的措施

1. **不要推送到远程仓库**
   ```powershell
   # 如果还没有 push，撤销最后一次提交
   git reset --soft HEAD~1
   ```

2. **如果已经推送**
   ```powershell
   # 立即更改所有暴露的密码、授权码
   # 重新生成 QQ 邮箱授权码
   # 重新获取 AnyRouter 的 session
   ```

3. **清理 Git 历史（谨慎操作）**
   ```powershell
   # 从所有提交历史中删除敏感文件
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```

4. **强制推送（会改写远程历史）**
   ```powershell
   git push origin --force --all
   ```

---

## 📞 快速命令参考

### 清理临时文件
```powershell
.\scripts\cleanup.ps1
```

### 检查 Git 状态
```powershell
git status
```

### 查看被忽略的文件
```powershell
git status --ignored
```

### 验证敏感文件已被忽略
```powershell
git check-ignore -v .env balance_hash.txt test_email.py
```

### 查看将要提交的差异
```powershell
git diff
```

---

## ✅ 当前状态确认

执行以下命令确认配置正确：

```powershell
# 1. 检查 .env 是否被忽略
git check-ignore -v .env
# 期望输出：.gitignore:15:.env    .env

# 2. 查看 Git 状态
git status
# 期望输出：不包含 .env 文件

# 3. 列出所有被追踪的文件
git ls-files
# 期望输出：不包含 .env、balance_hash.txt 等敏感文件
```

---

## 🎯 总结

✅ **已完成的安全措施：**
1. 更新 `.gitignore` 文件，包含所有敏感文件
2. 清理临时文件和缓存
3. 验证 `.env` 不会被 Git 追踪
4. 创建安全的配置模板 `.env.example`
5. 提供完整的安全检查清单

✅ **你的敏感信息现在是安全的：**
- 本地 `.env` 文件不会被提交
- GitHub Actions 使用 Environment Secrets
- 所有临时文件都被清理
- Git 仓库中不包含任何敏感信息

🎉 **可以安全地提交代码了！**
