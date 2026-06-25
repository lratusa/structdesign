# -*- coding: utf-8 -*-
"""
structdesign 测试界面启动器。

用法（本机必须用 python=3.9.7，不要用 python3=3.13 没装 numpy）：
    python run_app.py
然后浏览器打开 http://127.0.0.1:5000
或双击 启动界面.bat
"""
import os
import sys
import webbrowser
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp"))

from webapp.app import app

URL = "http://127.0.0.1:5000"


def _open():
    # Flask reloader 关闭时本进程即服务进程；延迟开浏览器
    import time
    time.sleep(1.2)
    try:
        webbrowser.open(URL)
    except Exception:
        pass


if __name__ == "__main__":
    print("=" * 56)
    print(" structdesign 测试界面")
    print(" 打开浏览器访问： " + URL)
    print(" 关闭：在本窗口按 Ctrl+C")
    print("=" * 56)
    threading.Thread(target=_open, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
