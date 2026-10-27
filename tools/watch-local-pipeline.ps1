param([switch]$Once)
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
. (Join-Path $PSScriptRoot 'controller-process.ps1')
$runtimeRoot = Join-Path $repoRoot '.cache/local-pipeline'
[IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null
$mutex = New-Object Threading.Mutex($false, 'Local\DailyArxivStartupWatcher')
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); exit 0 }
try {
    $runtimeConfig = Get-Content -LiteralPath (Join-Path $runtimeRoot 'runtime.json') -Raw | ConvertFrom-Json
    $pythonPath = $runtimeConfig.python
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Configured Python executable is unavailable.' }
    do {
        try {
            $app = @(Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | Where-Object {
                $_.Path -and ($_.Path -like '*\WindowsApps\OpenAI.Codex_*\app\ChatGPT.exe' -or $_.Path -like '*\app\Codex.exe')
            })
            if ($app.Count -gt 0) {
                $planResult = Invoke-ArxivController $pythonPath (Join-Path $repoRoot 'tools/local_pipeline.py') @('plan')
                if ($planResult.Stderr) { Add-Content -LiteralPath (Join-Path $runtimeRoot 'watcher.log') -Value $planResult.Stderr -Encoding UTF8 }
                if ($planResult.ExitCode -ne 0) { throw 'Could not inspect the catch-up queue.' }
                $plan = $planResult.Stdout | ConvertFrom-Json
                if ($plan.enabled -ne $false -and @($plan.due).Count -gt 0) {
                    $runResult = Invoke-ArxivController $pythonPath (Join-Path $repoRoot 'tools/local_pipeline.py') @('run','--automatic')
                    foreach ($outputText in @($runResult.Stdout, $runResult.Stderr)) {
                        if ($outputText) { Add-Content -LiteralPath (Join-Path $runtimeRoot 'watcher.log') -Value $outputText -Encoding UTF8 }
                    }
                    if ($runResult.ExitCode -ne 0) { throw ('Controller exited with code {0}; see preceding log.' -f $runResult.ExitCode) }
                }
            }
        } catch {
            ('{0:o} Watcher check failed: {1}' -f [DateTimeOffset]::UtcNow, $_.Exception.Message) | Add-Content -LiteralPath (Join-Path $runtimeRoot 'watcher.log')
        }
        if (-not $Once) { Start-Sleep -Seconds 60 }
    } while (-not $Once)
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
