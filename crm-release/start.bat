@echo off
rem CRM 本地一键启动（Windows）
rem 首次运行自动创建虚拟环境并安装依赖，之后直接启动
chcp 65001 >nul
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo 错误：未找到 python，请先安装 Python 3.10+  https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

rem 1. 虚拟环境（仅首次创建）
if not exist .venv (
    echo ── 首次运行：创建虚拟环境 ──
    python -m venv .venv
)
call .venv\Scripts\activate.bat

rem 2. 依赖
if not exist .venv\.deps-ok (
    echo ── 安装依赖（首次约 1-2 分钟）──
    python -m pip install -q --upgrade pip
    python -m pip install -q -r requirements.txt
    echo ok> .venv\.deps-ok
)

rem 3. 启动生产服务器（waitress 多线程）
if "%CRM_PORT%"=="" set CRM_PORT=5001
echo.
echo ══════════════════════════════════════════════
echo   林业无人机 CRM 已启动
echo   访问地址: http://localhost:%CRM_PORT%
echo   数据文件: %cd%\instance\crm.db
echo   停止服务: 关闭本窗口或 Ctrl+C
echo ══════════════════════════════════════════════
waitress-serve --host=0.0.0.0 --port=%CRM_PORT% --threads=8 wsgi:app
pause
