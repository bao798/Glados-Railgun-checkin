# Run locally with Windows PowerShell. Credentials never enter GitHub.
$ErrorActionPreference = 'Stop'
$state = Join-Path $env:LOCALAPPDATA 'GladosLocalCheckin'
New-Item -ItemType Directory -Force -Path $state | Out-Null
$config = @()
foreach ($number in 1,2) {
    Write-Host "Account $number - paste the complete Cookie from your own GLaDOS browser."
    $cookie = Read-Host 'Cookie (hidden input)' -AsSecureString
    $ua = Read-Host 'User-Agent from the same browser'
    if ([string]::IsNullOrWhiteSpace($ua)) { throw 'User-Agent is required.' }
    $config += [PSCustomObject]@{ Slot=$number; Cookie=$cookie; UserAgent=$ua }
}
# Export-Clixml encrypts SecureString with Windows DPAPI, bound to this user/device.
$config | Export-Clixml -LiteralPath (Join-Path $state 'accounts.xml')
Write-Host 'Saved encrypted credentials locally. No credentials were uploaded.'
