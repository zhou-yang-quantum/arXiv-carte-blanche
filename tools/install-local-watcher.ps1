param([switch]$StartNow)
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$watcherPath = Join-Path $repoRoot 'tools/watch-local-pipeline.ps1'
$runtimeRoot = Join-Path $repoRoot '.cache/local-pipeline'
if (-not (Test-Path -LiteralPath $watcherPath)) { throw 'Watcher script is missing.' }
[IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$codexPath = (Get-Command codex -ErrorAction Stop).Source
$runtimePath = Join-Path $runtimeRoot 'runtime.json'
$runtime = @{python=$pythonPath; codex=$codexPath}
[IO.File]::WriteAllText($runtimePath, (($runtime | ConvertTo-Json) + "`n"), (New-Object Text.UTF8Encoding($false)))
$userName = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskName = 'Daily-arXiv startup catch-up'
$powershellPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $watcherPath + '"'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    $matchingAction = @($existing.Actions | Where-Object { $_.Execute -eq $powershellPath -and $_.Arguments -eq $arguments })
    if ($matchingAction.Count -ne 1) { throw 'A different task already uses this name; refusing to replace it.' }
}
$action = New-ScheduledTaskAction -Execute $powershellPath -Argument $arguments -WorkingDirectory $repoRoot
$loginTrigger = New-ScheduledTaskTrigger -AtLogOn -User $userName
# Restart an interrupted watcher without waiting for another Windows login.
# IgnoreNew below keeps these periodic starts from duplicating a running watcher.
$restartTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($loginTrigger, $restartTrigger) -Principal $principal -Settings $settings -Description 'Check the daily-arXiv catch-up queue after login and when Codex opens; restart an interrupted watcher every five minutes. No AI calls when nothing is due.' -Force | Out-Null
if ($StartNow) { Start-ScheduledTask -TaskName $taskName }
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State,@{Name='RunAs';Expression={$_.Principal.UserId}} | ConvertTo-Json -Compress
