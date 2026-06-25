# structdesign Modeler - per-user installer (no admin). ASCII-only for encoding safety.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src  = Join-Path $here 'structdesign_modeler'
$dest = Join-Path $env:LOCALAPPDATA 'Programs\structdesign_modeler'
$shortcut = 'structdesign modeler.lnk'

Write-Host '============================================================'
Write-Host ' structdesign Modeler - Installer (per-user, no admin)'
Write-Host ' structdesign jianmoqi - install to current user'
Write-Host '============================================================'

if (-not (Test-Path (Join-Path $src 'structdesign_modeler.exe'))) {
    Write-Host '[ERROR] structdesign_modeler\structdesign_modeler.exe NOT found.'
    Write-Host '        Please FULLY extract the whole zip first, then run again.'
    return
}

Write-Host ("Install to: " + $dest)
Write-Host 'Copying files (a few hundred MB), please wait ...'
robocopy $src $dest /E /NFL /NDL /NJH /NJS /NP | Out-Null
$exe = Join-Path $dest 'structdesign_modeler.exe'
if (-not (Test-Path $exe)) { Write-Host '[ERROR] copy failed.'; return }

Write-Host 'Creating Desktop / Start Menu shortcuts ...'
$w = New-Object -ComObject WScript.Shell
$targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
)
foreach ($p in $targets) {
    $lnk = $w.CreateShortcut((Join-Path $p $shortcut))
    $lnk.TargetPath = $exe
    $lnk.WorkingDirectory = $dest
    $lnk.Save()
}

Write-Host ''
Write-Host '[DONE] Installed OK.'
Write-Host ('  Program : ' + $exe)
Write-Host '  Shortcut: "structdesign modeler" on Desktop and Start Menu.'
Write-Host '  Outputs : %USERPROFILE%\structdesign_work\'
Write-Host '  Uninstall: run uninstall (juanzai).bat'
$ans = Read-Host 'Launch now? (Y/N)'
if ($ans -eq 'Y' -or $ans -eq 'y') { Start-Process $exe }
