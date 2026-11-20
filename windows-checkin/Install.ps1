$ErrorActionPreference = 'Stop'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 22 LTS or later from https://nodejs.org/ and run this script again.'
}
if (-not (Test-Path (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe')) -and
    -not (Test-Path (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'))) {
    throw 'Microsoft Edge must be installed.'
}
Push-Location $PSScriptRoot
try {
    & npm.cmd ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & node --test
    if ($LASTEXITCODE -ne 0) { throw 'Checks failed.' }
} finally { Pop-Location }
& (Join-Path $PSScriptRoot 'Configure.ps1')
$runner = Join-Path $PSScriptRoot 'Run.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -File "' + $runner + '"')
$triggers = @()
$bjToday = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'China Standard Time').ToString('yyyy-MM-dd')
foreach ($hour in 8,12,18,22) {
    $trigger = New-ScheduledTaskTrigger -Daily -At ("{0:00}:47" -f $hour)
    $trigger.StartBoundary = ("{0}T{1:00}:47:00+08:00" -f $bjToday,$hour)
    $triggers += $trigger
}
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName 'GLaDOS Local Checkin' -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Force | Out-Null
Write-Host 'Scheduled: 08:47, 12:47, 18:47, 22:47 Beijing time.'
Write-Host 'Task runs only while this user is logged in. No Windows time-zone change is made.'
Write-Host 'Run .\Run.ps1 -TestRun now and inspect both account results.'
