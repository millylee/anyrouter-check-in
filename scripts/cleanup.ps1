#!/usr/bin/env pwsh
# 清理项目临时文件和测试文件

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "清理项目临时文件" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# 要清理的文件和目录
$itemsToClean = @(
    "test_email.py",           # 测试脚本
    "balance_hash.txt",        # 余额缓存
    "__pycache__",             # Python 缓存
    ".pytest_cache",           # Pytest 缓存
    ".ruff_cache",             # Ruff 缓存
    "*.pyc",                   # Python 编译文件
    "*.pyo",                   # Python 优化文件
    "*.log",                   # 日志文件
    ".DS_Store",               # macOS 文件
    "Thumbs.db"                # Windows 文件
)

$cleaned = 0

foreach ($item in $itemsToClean) {
    $found = Get-ChildItem -Path . -Filter $item -Recurse -Force -ErrorAction SilentlyContinue
    
    if ($found) {
        foreach ($file in $found) {
            try {
                if ($file.PSIsContainer) {
                    Remove-Item -Path $file.FullName -Recurse -Force
                    Write-Host "✅ 已删除目录: $($file.FullName)" -ForegroundColor Green
                } else {
                    Remove-Item -Path $file.FullName -Force
                    Write-Host "✅ 已删除文件: $($file.FullName)" -ForegroundColor Green
                }
                $cleaned++
            }
            catch {
                Write-Host "❌ 无法删除: $($file.FullName)" -ForegroundColor Red
            }
        }
    }
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "✅ 清理完成！共清理 $cleaned 项" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "注意：.env 文件（包含敏感信息）已被保留" -ForegroundColor Yellow
Write-Host "该文件不会被 Git 追踪" -ForegroundColor Yellow
