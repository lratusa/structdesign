@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动 structdesign 测试界面 ... 浏览器将自动打开 http://127.0.0.1:5000
echo 关闭：在本窗口按 Ctrl+C
python run_app.py
pause
