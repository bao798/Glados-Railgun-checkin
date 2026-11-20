param([switch]$TestRun)
$ErrorActionPreference = 'Stop'
$state = Join-Path $env:LOCALAPPDATA 'GladosLocalCheckin'
$lock = New-Object System.Threading.Mutex($false, 'Local\GladosLocalCheckin')
if (-not $lock.WaitOne(0)) { exit 0 }
$exitCode = 1
try {
    $accounts = @(Import-Clixml -LiteralPath (Join-Path $state 'accounts.xml'))
    if ($accounts.Count -ne 2) { throw 'Configure both accounts first.' }
    foreach ($account in $accounts) {
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($account.Cookie)
        try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
        $key = if ($account.Slot -eq 1) { 'GLADOS' } else { 'GLADOS2' }
        [Environment]::SetEnvironmentVariable($key, $plain, 'Process')
        [Environment]::SetEnvironmentVariable("GLADOS_UA$($account.Slot)", $account.UserAgent, 'Process')
        if ($account.Slot -eq 1) { $env:GLADOS_UA = $account.UserAgent }
        $plain = $null
    }
    $env:DOMAIN = 'glados.cloud'
    $env:BROWSER_HEADED = '1'
    $env:BROWSER_CLICK = 'false'
    $env:AUTO_EXCHANGE = 'false'
    $env:NOTIFY = ''
    $env:GITHUB_EVENT_NAME = 'workflow_dispatch'
    Push-Location $PSScriptRoot
    try {
        if ($TestRun) { & node main.js; $exitCode = $LASTEXITCODE }
        else { & node main.js *> (Join-Path $state 'latest.log'); $exitCode = $LASTEXITCODE }
    } finally { Pop-Location }
} catch {
    if ($TestRun) { Write-Host $_.Exception.Message }
    else { $_.Exception.Message | Out-File -LiteralPath (Join-Path $state 'latest.log') -Encoding utf8 }
} finally {
    foreach ($key in 'GLADOS','GLADOS2','GLADOS_UA','GLADOS_UA1','GLADOS_UA2') {
        [Environment]::SetEnvironmentVariable($key, $null, 'Process')
    }
    $lock.ReleaseMutex(); $lock.Dispose()
}
if ($exitCode -ne 0 -and -not $TestRun) {
    # Only an error opens a local message. Successful scheduled runs stay quiet.
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "GLaDOS check-in needs attention. See $state\latest.log",
        'GLaDOS check-in failed') | Out-Null
}
exit $exitCode
