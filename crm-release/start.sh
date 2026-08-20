#!/bin/bash
# CRM 本地一键启动（macOS / Linux）
# 首次运行自动创建虚拟环境并安装依赖，之后直接启动
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "错误：未找到 python3，请先安装 Python 3.10+  https://www.python.org/downloads/"
    exit 1
fi

# 1. 虚拟环境（仅首次创建）
if [ ! -d .venv ]; then
    echo "── 首次运行：创建虚拟环境 ──"
    "$PY" -m venv .venv
fi
source .venv/bin/activate

# 2. 依赖（有变化时安装；requirements.lock 存在则跳过重复安装）
if [ ! -f .venv/.deps-ok ] || [ requirements.txt -nt .venv/.deps-ok ]; then
    echo "── 安装依赖（首次约 1-2 分钟）──"
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    touch .venv/.deps-ok
fi

# 3. 启动生产服务器（waitress 多线程）
PORT="${CRM_PORT:-5001}"
echo ""
echo "══════════════════════════════════════════════"
echo "  林业无人机 CRM 已启动"
echo "  访问地址: http://localhost:${PORT}"
echo "  数据文件: $(pwd)/instance/crm.db"
echo "  停止服务: Ctrl+C"
echo "══════════════════════════════════════════════"
exec waitress-serve --host=0.0.0.0 --port="$PORT" --threads=8 wsgi:app
