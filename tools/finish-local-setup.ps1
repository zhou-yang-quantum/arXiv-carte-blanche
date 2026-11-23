# Run interactively after installing the watcher on a new Windows computer.
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtimePath = Join-Path $repoRoot '.cache/local-pipeline/runtime.json'
if (-not (Test-Path -LiteralPath $runtimePath)) { throw 'Install the local watcher first.' }
$runtime = Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json
# Include tools installed since this terminal or Task Scheduler started.
$env:PATH = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:PATH
$toolDirectories = @($runtime.python, $runtime.codex, $runtime.gh) |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    ForEach-Object { [IO.Path]::GetDirectoryName($_) } |
    Select-Object -Unique
$env:PATH = ($toolDirectories -join ';') + ';' + $env:PATH
$githubPath = $runtime.gh
if (-not $githubPath) { $githubPath = (Get-Command gh -ErrorAction Stop).Source }
foreach ($executable in @($runtime.python, $runtime.codex, $githubPath)) {
    if (-not $executable -or -not (Test-Path -LiteralPath $executable)) {
        throw 'A configured tool is unavailable; reinstall the watcher with this computer''s executable paths.'
    }
}
Push-Location $repoRoot
try {
    & $githubPath auth status --hostname github.com
    if ($LASTEXITCODE -ne 0) {
        & $githubPath auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { throw 'GitHub login was not completed.' }
    }
    $repository = & $runtime.python -c 'from tools.project import REPOSITORY; print(REPOSITORY)'
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the project repository.' }
    $canPublish = & $githubPath api ('repos/' + $repository.Trim()) --jq '.permissions.push'
    if ($LASTEXITCODE -ne 0 -or $canPublish -ne 'true') {
        throw 'Sign in to a GitHub account with write access to the project repository.'
    }
    & $githubPath auth setup-git --hostname github.com
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure GitHub HTTPS authentication.' }
    & $runtime.codex -c 'forced_login_method=chatgpt' login status
    if ($LASTEXITCODE -ne 0) { throw 'Complete codex login using ChatGPT before resuming.' }
    # Release the machine-wide authentication cooldown under the controller lock.
    # Preserve all per-date retry, review, and completed-research records.
    $clearCooldown = @'
from tools import local_pipeline as pipeline
with pipeline.pipeline_lock() as acquired:
    if not acquired:
        raise SystemExit('A worker is active; run this completion command after it finishes.')
    state = pipeline.read_state()
    state.pop('pause_until', None)
    pipeline.save_state(state)
'@
    & $runtime.python -c $clearCooldown
    if ($LASTEXITCODE -ne 0) { throw 'Could not clear the authentication retry delay.' }
    $watcher = Get-ScheduledTask -TaskName 'Daily-arXiv startup catch-up'
    if ($watcher.State -ne 'Running') { Start-ScheduledTask -TaskName $watcher.TaskName }
    & $runtime.python tools/local_pipeline.py plan
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the restored queue.' }
    Write-Output 'Setup complete. Keep Codex open; the watcher checks the queue once per minute.'
} finally { Pop-Location }
