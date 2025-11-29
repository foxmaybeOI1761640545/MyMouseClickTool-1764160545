$ErrorActionPreference = "Stop"
if ($PSScriptRoot) { $ScriptDir = $PSScriptRoot } else { $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
if ($ScriptDir) { Set-Location $ScriptDir }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WaveNumberOCR - 安装和启动脚本" -ForegroundColor Cyan
Write-Host "  屏幕区域标记器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] 检查 Python 环境..." -ForegroundColor Yellow
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "  错误: 未找到 Python" -ForegroundColor Red
    Write-Host "  请先安装 Python 3.7 或更高版本" -ForegroundColor Yellow
    Write-Host "  下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按 Enter 键退出"
    exit 1
}
$pythonVersion = python --version 2>&1
Write-Host "  找到 Python: $pythonVersion" -ForegroundColor Green

Write-Host "[2/4] 检查 pip..." -ForegroundColor Yellow
$pipCmd = Get-Command pip -ErrorAction SilentlyContinue
if (-not $pipCmd) {
    Write-Host "  错误: 未找到 pip" -ForegroundColor Red
    Write-Host ""
    Read-Host "按 Enter 键退出"
    exit 1
}
$pipVersion = pip --version 2>&1
Write-Host "  找到 pip: $pipVersion" -ForegroundColor Green

Write-Host "[3/4] 检查依赖文件..." -ForegroundColor Yellow
if (-not (Test-Path "requirements.txt")) {
    Write-Host "  错误: 未找到 requirements.txt" -ForegroundColor Red
    Write-Host ""
    Read-Host "按 Enter 键退出"
    exit 1
}
Write-Host "  找到 requirements.txt" -ForegroundColor Green

Write-Host "[4/4] 安装依赖包..." -ForegroundColor Yellow
Write-Host "  正在安装依赖，请稍候..." -ForegroundColor Gray
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  依赖安装失败" -ForegroundColor Red
    Write-Host ""
    Read-Host "按 Enter 键退出"
    exit 1
}
Write-Host "  依赖安装成功" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动 WaveNumberOCR 应用程序..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 关键修改：从根目录运行 app\main.py
python .\app\main.py
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "程序运行出错，退出码: $exitCode" -ForegroundColor Red
    Write-Host ""
}

Write-Host ""
Read-Host "程序已退出，按 Enter 键关闭窗口"
exit $exitCode
