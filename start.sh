#!/bin/bash
# CRM 服务启动入口。
# 端口统一由 CRM_PORT 环境变量控制，默认 5003（唯一来源在 app.py），
# 避免此前 start.sh/run_local.py 各写一个端口导致「到底该访问哪个端口」的混乱。
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python app.py
