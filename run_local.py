#!/usr/bin/env python3
"""本地启动脚本（仅监听 127.0.0.1，不对外暴露）。

与项目自带的 app.py 的区别：app.py 绑定 0.0.0.0 且端口固定 5001，
本脚本只监听回环地址，便于本机验证。

用法：
    CRM_PORT=5001 python run_local.py
"""
import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(
        host='127.0.0.1',
        port=int(os.environ.get('CRM_PORT', '5001')),
        debug=False,
        use_reloader=False,
        threaded=True,
    )
