function Invoke-ArxivController {
    param(
        [string]$PythonPath,
        [string]$ScriptPath,
        [ValidateSet('plan','run','--automatic')][string[]]$ControllerArguments = @()
    )
    # Read both streams without PowerShell interpreting native stderr as an error.
    # In particular, a warning must not kill a successful controller process.
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $PythonPath
    $info.Arguments = '"' + $ScriptPath + '" ' + ($ControllerArguments -join ' ')
    $info.WorkingDirectory = [IO.Path]::GetDirectoryName($ScriptPath)
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = New-Object Text.UTF8Encoding($false)
    $info.StandardErrorEncoding = New-Object Text.UTF8Encoding($false)
    $info.EnvironmentVariables['PYTHONUTF8'] = '1'
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        $process.Start() | Out-Null
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        return [PSCustomObject]@{
            ExitCode = $process.ExitCode
            Stdout = $stdout.GetAwaiter().GetResult()
            Stderr = $stderr.GetAwaiter().GetResult()
        }
    } finally { $process.Dispose() }
}
