; structdesign 建模器 Windows 安装包脚本（Inno Setup 6）
; 用法：装免费的 Inno Setup（https://jrsoftware.org/isdl.php）后，
;   右键本文件「Compile」，或命令行：
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; 前提：已先用 PyInstaller 生成 dist\structdesign_modeler\（见 build_installer.bat）。
; 产物：Output\structdesign_modeler_setup.exe —— 发给试用人员，双击安装即用。

#define AppName "structdesign 建模器"
#define AppVer "0.1.0"
#define ExeName "structdesign_modeler.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=structdesign
DefaultDirName={autopf}\structdesign_modeler
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=structdesign_modeler_setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
; 安装包较大(含 PyQt5/matplotlib/plotly)，约数百 MB

[Languages]
Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
Source: "dist\structdesign_modeler\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent
