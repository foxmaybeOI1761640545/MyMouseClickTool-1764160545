@echo off
chcp 65001 >nul
mode con: cols=15 lines=3
cd /d "%~dp0"

echo ========================================
echo   ScreenRegionMarker - 安装和启动脚本
echo   屏幕区域标记器
echo ========================================
echo.

echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo   错误: 未找到 Python，请先安装 Python 3.7 或更高版本
    echo   下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo   找到 Python: %PYTHON_VERSION%

echo [2/4] 检查 pip...
pip --version >nul 2>&1
if errorlevel 1 (
    echo   错误: 未找到 pip
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('pip --version 2^>^&1') do set PIP_VERSION=%%i
echo   找到 pip: %PIP_VERSION%

echo [3/4] 检查依赖文件...
if not exist "requirements.txt" (
    echo   错误: 未找到 requirements.txt
    echo.
    pause
    exit /b 1
)
echo   找到 requirements.txt

echo [4/4] 安装依赖包...
echo   正在安装依赖，请稍候...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo   依赖安装失败
    echo.
    pause
    exit /b 1
)
echo   依赖安装成功

echo.
echo ========================================
echo   启动 ScreenRegionMarker 应用程序...
echo ========================================
echo.

rem 关键修改：从根目录运行 app\main.py
python app\main.py

if errorlevel 1 (
    echo.
    echo 程序运行出错，退出码: %ERRORLEVEL%
    echo.
)

echo.
echo 程序已退出，按任意键关闭窗口...
pause >nul
