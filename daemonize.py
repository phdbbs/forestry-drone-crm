#!/usr/bin/env python3
"""以守护进程方式启动 CRM 服务，脱离终端会话独立运行。

背景：此前服务是用「会话后台任务」启动的，会话（终端 / WorkBuddy）一关，
进程就被系统回收，表现为「打开页面没反应、端口都连不上」。
这里用标准的双 fork + setsid，让服务成为独立会话的进程并被系统收养（ppid=1），
父进程退出不再影响它。

用法：
    ./.venv/bin/python daemonize.py          # 启动（已在运行则忽略）
    ./.venv/bin/python daemonize.py stop     # 停止
    ./.venv/bin/python daemonize.py status   # 查看状态
"""
import os
import signal
import sys
import time

BASE_DIR = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
INSTANCE_DIR = os.path.realpath(os.path.join(BASE_DIR, 'instance'))
# 落盘路径统一 realpath 归一化并限定在项目目录内（防 ../ 越界）
PID_FILE = os.path.realpath(os.path.join(INSTANCE_DIR, 'crm.pid'))
LOG_FILE = os.path.realpath(os.path.join(INSTANCE_DIR, 'crm-daemon.log'))
if not PID_FILE.startswith(INSTANCE_DIR + os.sep) or not LOG_FILE.startswith(INSTANCE_DIR + os.sep):
    raise RuntimeError('路径越界，拒绝启动')
PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python')


def _read_pid():
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop():
    pid = _read_pid()
    if not _alive(pid):
        print('服务未运行')
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not _alive(pid):
            break
        time.sleep(0.3)
    else:
        os.kill(pid, signal.SIGKILL)
    try:
        os.remove(PID_FILE)
    except OSError:
        pass
    print(f'已停止服务 (PID {pid})')


def status():
    pid = _read_pid()
    print(f'运行中 (PID {pid})' if _alive(pid) else '未运行')


def start():
    if _alive(_read_pid()):
        print(f'服务已在运行 (PID {_read_pid()})')
        return
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    # 第一次 fork：父进程立刻返回，让调用方（shell）结束而不阻塞
    if os.fork() > 0:
        return
    os.setsid()  # 成为新会话首进程：脱离原会话、断开终端
    # 第二次 fork：确保不再是会话首进程，永远不会重新获得控制终端
    if os.fork() > 0:
        os._exit(0)
    os.chdir(BASE_DIR)
    os.umask(0o022)
    with open(LOG_FILE, 'ab', buffering=0) as log, open(os.devnull, 'rb') as null:
        os.dup2(null.fileno(), 0)
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
    # FD 方式写 PID 文件（PID_FILE/LOG_FILE 在模块头已做 realpath 越界校验，限定在 instance/ 内）
    fd = os.open(PID_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, str(os.getpid()).encode())
    finally:
        os.close(fd)
    # 进程内执行 app.py（run_name='__main__' 触发其中的 app.run 阻塞循环）：
    # 守护进程即服务进程，stop() 的 SIGTERM 直达服务，无需 execv/子进程转发。
    import runpy
    runpy.run_path(os.path.join(BASE_DIR, 'app.py'), run_name='__main__')


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'start'
    if action == 'stop':
        stop()
    elif action == 'status':
        status()
    else:
        start()
