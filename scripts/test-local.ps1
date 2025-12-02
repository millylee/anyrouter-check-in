#!/usr/bin/env pwsh
# AnyRouter 自动签到 - 本地测试脚本

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "AnyRouter 自动签到 - 本地测试" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# 检查 .env 文件
if (!(Test-Path ".env")) {
    Write-Host "❌ 错误: .env 文件不存在" -ForegroundColor Red
    Write-Host "请先创建 .env 文件并配置账号信息" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ 找到 .env 配置文件" -ForegroundColor Green

# 检查虚拟环境
if (!(Test-Path ".venv")) {
    Write-Host "📦 安装依赖..." -ForegroundColor Yellow
    uv sync
    Write-Host "✅ 依赖安装完成" -ForegroundColor Green
    Write-Host ""
}

# 检查 Playwright 浏览器
Write-Host "🌐 检查 Playwright 浏览器..." -ForegroundColor Yellow
$playwrightCheck = & uv run python -c "from playwright.sync_api import sync_playwright; print('ok')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "📥 安装 Playwright 浏览器..." -ForegroundColor Yellow
    uv run playwright install chromium
    Write-Host "✅ 浏览器安装完成" -ForegroundColor Green
}

Write-Host ""
Write-Host "🚀 开始运行签到脚本..." -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# 运行签到脚本
uv run python checkin.py

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "✅ 测试完成！" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
