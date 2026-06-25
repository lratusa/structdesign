@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  structdesign 建模器 - 打包构建
echo ============================================================
echo [1/3] PyInstaller 生成免安装程序 dist\structdesign_modeler\ ...
python -m PyInstaller structdesign_modeler.spec --noconfirm
if errorlevel 1 ( echo PyInstaller 失败 & pause & exit /b 1 )

echo [2/3] 打包便携版 zip（可直接发给试用人员，解压即用）...
powershell -NoProfile -Command ^
  "Compress-Archive -Path 'dist\structdesign_modeler\*' -DestinationPath 'dist\structdesign_modeler_portable.zip' -Force"

echo [3/3] 生成安装包 setup.exe（需已安装 Inno Setup 6）...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% installer.iss
    echo 安装包已生成: Output\structdesign_modeler_setup.exe
) else (
    echo 未检测到 Inno Setup，跳过 setup.exe。可装 https://jrsoftware.org/isdl.php 后再跑本脚本，
    echo 或直接分发便携版 dist\structdesign_modeler_portable.zip。
)
echo ============================================================
echo  完成。免安装程序: dist\structdesign_modeler\structdesign_modeler.exe
echo ============================================================
pause
