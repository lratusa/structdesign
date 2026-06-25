@echo off
rem ASCII-only launcher; all logic in install.ps1 (avoids cmd codepage issues with Chinese)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
