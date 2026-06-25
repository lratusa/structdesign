# structdesign Modeler - uninstaller (per-user). ASCII-only.
$dest = Join-Path $env:LOCALAPPDATA 'Programs\structdesign_modeler'
$shortcut = 'structdesign modeler.lnk'
# use cmd rmdir /s /q (more robust than Remove-Item for PyInstaller _internal deep nested paths)
if (Test-Path $dest) { cmd /c ('rmdir /s /q "' + $dest + '"') | Out-Null }
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue }
Remove-Item -Force (Join-Path ([Environment]::GetFolderPath('Desktop')) $shortcut) -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $env:APPDATA ('Microsoft\Windows\Start Menu\Programs\' + $shortcut)) -ErrorAction SilentlyContinue
Write-Host 'Uninstalled. (Outputs in %USERPROFILE%\structdesign_work kept; delete manually if not needed.)'
