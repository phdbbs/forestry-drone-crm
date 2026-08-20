#!/bin/bash
# CRM 正式应用守护脚本：gunicorn 崩溃后 3 秒自动拉起
# 用法: setsid nohup /workspace/crm-prod/run.sh > /dev/null 2>&1 &
set -u
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON=/root/.pyenv/versions/3.14.7/bin/python
export CRM_PORT="${CRM_PORT:-5001}"

cd "$BASE_DIR"
echo "$(date '+%F %T') CRM 守护进程启动 (端口 $CRM_PORT)"

while true; do
    "$PYTHON" -m gunicorn -c gunicorn.conf.py wsgi:app
    code=$?
    echo "$(date '+%F %T') gunicorn 退出码 $code，3 秒后自动重启"
    sleep 3
done
