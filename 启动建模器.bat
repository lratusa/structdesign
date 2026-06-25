@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动 structdesign 建模器 ...
python launch_modeler.py
pause
