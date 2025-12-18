#!/bin/bash

# AnyRouter/AgentRouter 自动签到脚本启动器

echo "===================================="
echo "AnyRouter/AgentRouter 自动签到工具"
echo "===================================="

# 检查配置文件
if [ -f "config.json" ]; then
    echo "✅ 发现配置文件 config.json"
    export ANYROUTER_ACCOUNTS=$(cat config.json)
    echo "✅ 配置已加载"
    echo "配置账户数: $(grep -c '\"provider\"' config.json)"
elif [ -f "accounts.env" ]; then
    echo "✅ 发现配置文件 accounts.env (兼容模式)"
    export ANYROUTER_ACCOUNTS=$(grep -v '^#' accounts.env | grep -v '^$' | grep 'ANYROUTER_ACCOUNTS=' | sed 's/ANYROUTER_ACCOUNTS=//')
    echo "✅ 配置已加载"
else
    echo "❌ 未找到配置文件"
    echo "请创建 config.json 或设置环境变量"
    exit 1
fi

# 检查Python依赖
echo ""
echo "检查Python依赖..."
python -c "import httpx, playwright" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 缺少依赖，正在安装..."
    pip install httpx playwright python-dotenv
fi

# 检查浏览器
echo "检查Playwright浏览器..."
if [ ! -d "$HOME/Library/Caches/ms-playwright/chromium-1200" ]; then
    echo "❌ 未安装Chromium，正在安装..."
    playwright install chromium
fi

echo ""
echo "开始执行签到任务..."
echo "===================================="

# 运行主脚本
export ANYROUTER_ACCOUNTS=$(cat config.json)
python checkin.py
EXIT_CODE=$?

echo ""
echo "===================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 签到任务完成 - 所有账户操作成功"
else
    echo "⚠️ 签到任务结束 - 检查日志详情"
fi

exit $EXIT_CODE