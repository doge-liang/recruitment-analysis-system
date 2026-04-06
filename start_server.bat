@echo off
chcp 65001 >nul
REM 启动招聘分析系统服务器 (Windows CMD)
REM 激活 conda 环境并启动 Django 开发服务器

echo ========================================
echo   招聘分析系统 - Windows 服务器启动器  
echo ========================================
echo.

REM 检查 conda
call conda --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 conda。请确保已安装 Miniconda 或 Anaconda。
    echo 下载地址: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

REM 激活 conda 环境
echo 正在激活 conda 环境 'recruitment'...
call conda activate recruitment

if errorlevel 1 (
    echo 错误: 无法激活环境 'recruitment'
    echo 请确保已创建环境: conda create -n recruitment python=3.10
    pause
    exit /b 1
)

echo 环境激活成功！
echo.

REM 检查 manage.py
if not exist "manage.py" (
    echo 错误: 未找到 manage.py
    echo 请确保在正确的目录中运行此脚本。
    pause
    exit /b 1
)

REM 启动服务器
echo 正在启动 Django 开发服务器...
echo 访问地址: http://localhost:8000/myApp/login/
echo 管理后台: http://localhost:8000/admin/
echo 爬虫管理: http://localhost:8000/myApp/admin/crawl/
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause
