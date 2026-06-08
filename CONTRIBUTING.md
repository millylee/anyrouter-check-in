# 贡献指南

感谢你有兴趣为 anyrouter-check-in 项目做出贡献！本文档将指导你如何参与项目开发。

## 📋 目录

- [开发环境设置](#开发环境设置)
- [代码规范](#代码规范)
- [提交代码](#提交代码)
- [运行测试](#运行测试)
- [提交 Pull Request](#提交-pull-request)
- [代码审查流程](#代码审查流程)

## 🛠️ 开发环境设置

### 前置要求

- Python 3.11 或更高版本
- [uv](https://docs.astral.sh/uv/) - Python 包管理工具
- Git

### 克隆仓库

```bash
git clone https://github.com/你的用户名/anyrouter-check-in.git
cd anyrouter-check-in
```

### 安装依赖

```bash
# 安装所有依赖（包括开发依赖）
uv sync --dev

# 安装 CloakBrowser 浏览器；也可以通过 CLOAKBROWSER_BINARY_PATH 指向本地浏览器
uv run python -m cloakbrowser install
```

### 配置环境变量

创建 `.env` 文件并配置测试账号信息：

```bash
# 示例配置（注意：JSON 必须是单行格式）
ANYROUTER_ACCOUNTS=[{"name":"测试账号","email":"your@email.com","password":"your_password"}]
```

### 安装 pre-commit 钩子

```bash
uv run pre-commit install
```

这将在每次提交前自动运行代码检查和格式化。

## 📝 代码规范

### Python 代码风格

本项目使用以下工具确保代码质量：

- **Ruff**: 代码风格检查和格式化
- **MyPy**: 静态类型检查
- **Bandit**: 安全漏洞扫描

### 代码风格要求

- 遵循 PEP 8 规范
- 最大行宽：120 字符
- 使用单引号（`'`）而非双引号（`"`）
- 使用 Tab 缩进
- 函数和方法应有适当的类型注解

### 运行代码检查

```bash
# 运行所有检查
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run bandit -r . -c pyproject.toml

# 自动修复代码风格问题
uv run ruff check . --fix
uv run ruff format .
```

### 使用 pre-commit

pre-commit 会在提交前自动运行检查：

```bash
# 手动运行 pre-commit 检查所有文件
uv run pre-commit run --all-files

# 如果需要跳过 pre-commit（不推荐）
git commit --no-verify
```

## 🔄 提交代码

### Commit 信息规范

使用语义化的 commit 信息：

```
<type>: <subject>

[optional body]

[optional footer]
```

**类型 (type):**

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例:**

```bash
feat: 添加 Bark 推送通知支持

添加了 Bark 推送服务的集成，用户可以通过配置 BARK_KEY 接收签到通知。

Closes #123
```

## 🧪 运行测试

### 运行所有测试

```bash
uv run pytest tests/
```

### 运行特定测试文件

```bash
uv run pytest tests/test_notify.py
```

### 查看测试覆盖率

```bash
uv run pytest tests/ --cov=. --cov-report=html
```

覆盖率报告将生成在 `htmlcov/index.html`。

### 编写测试

- 测试文件命名：`test_*.py`
- 测试函数命名：`test_*`
- 使用 `pytest` 框架
- 异步测试使用 `pytest-asyncio`
- 尽可能使用 mock 避免实际网络请求

**示例:**

```python
import pytest
from unittest.mock import patch

def test_parse_cookies():
    from checkin import parse_cookies

    # 测试字典格式
    cookies = {"session": "abc123"}
    result = parse_cookies(cookies)
    assert result == {"session": "abc123"}

    # 测试字符串格式
    cookies_str = "session=abc123; user=test"
    result = parse_cookies(cookies_str)
    assert result == {"session": "abc123", "user": "test"}

@pytest.mark.asyncio
async def test_check_in_account():
    # 异步测试示例
    pass
```

## 🚀 提交 Pull Request

### 1. Fork 项目

在 GitHub 上点击 "Fork" 按钮。

### 2. 创建特性分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/your-bug-fix
```

### 3. 提交改动

```bash
git add .
git commit -m "feat: your feature description"
```

### 4. 推送到你的 Fork

```bash
git push origin feature/your-feature-name
```

### 5. 创建 Pull Request

1. 访问你的 Fork 仓库
2. 点击 "Compare & pull request"
3. 填写 PR 模板中的信息
4. 提交 PR

### PR 检查清单

在提交 PR 前，请确保：

- [ ] 代码已通过本地所有测试
- [ ] 已添加必要的测试用例
- [ ] 代码符合项目规范（通过 ruff、mypy 检查）
- [ ] 更新了相关文档
- [ ] Commit 信息清晰明确
- [ ] 没有合并冲突

## 🔍 代码审查流程

提交 PR 后，会自动运行以下检查：

1. **pre-commit.ci**: 自动修复代码风格问题
2. **GitHub Actions**: 运行完整的质量检查
   - Ruff Lint（代码风格）
   - Ruff Format（代码格式）
   - MyPy（类型检查）
   - Bandit（安全扫描）
   - Pytest（测试）
3. **Codecov**: 报告测试覆盖率变化

### 审查标准

- 代码风格和格式必须通过检查
- 所有测试必须通过
- 测试覆盖率不应显著下降（不超过 5%）
- 类型检查和安全扫描的警告需要合理说明
- 代码逻辑清晰、易于维护
- 必要的注释和文档

### 修改 PR

如果审查者提出修改意见：

```bash
# 在你的特性分支上进行修改
git add .
git commit -m "fix: 根据审查意见进行修改"
git push origin feature/your-feature-name
```

PR 会自动更新，无需创建新的 PR。

## 🤝 社区规范

- 尊重所有贡献者
- 保持讨论专业和建设性
- 接受建设性的批评
- 关注项目的最佳利益

## 📞 获取帮助

如果你有任何问题：

- 查看现有的 [Issues](https://github.com/millylee/anyrouter-check-in/issues)
- 创建新的 Issue 描述你的问题
- 在 PR 中 @维护者 寻求帮助

## 📄 许可证

通过贡献代码，你同意你的贡献将按照项目的许可证授权。

---

再次感谢你的贡献！🎉
