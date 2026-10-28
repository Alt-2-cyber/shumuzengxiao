param(
    [string]$DriveRoot,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

function Convert-MaixCamConsoleConfig {
    param([Parameter(Mandatory)][byte[]]$Bytes)

    if ($Bytes -contains [byte]0) { throw 'uEnv.txt contains binary data.' }
    $hasBom = $Bytes.Length -ge 3 -and $Bytes[0] -eq 239 -and $Bytes[1] -eq 187 -and $Bytes[2] -eq 191
    $offset = if ($hasBom) { 3 } else { 0 }
    $encoding = [Text.UTF8Encoding]::new($false, $true)
    $content = $encoding.GetString($Bytes, $offset, $Bytes.Length - $offset)
    $pattern = '(?m)^([ \t]*)(consoledev[ \t]*=[^\r\n]*)(\r?)$'
    $matchesFound = [regex]::Matches($content, $pattern).Count
    $updated = [regex]::Replace($content, $pattern, '$1# $2$3')
    [byte[]]$result = $encoding.GetBytes($updated)
    if ($hasBom) { $result = [byte[]](@(239, 187, 191) + $result) }
    return [pscustomobject]@{ Bytes = $result; ChangedLines = $matchesFound }
}

if ($MyInvocation.InvocationName -eq '.') { return }
if (-not $DriveRoot -or $DriveRoot -notmatch '^[A-Za-z]:[\\/]?$') {
    throw 'Specify the TF boot volume, for example: -DriveRoot E:\ . Default is inspection only; add -Apply to enable the console.'
}
$letter = $DriveRoot.Substring(0, 1).ToUpperInvariant()
$root = $letter + ':\'
$volume = Get-Volume -DriveLetter $letter
$disks = @(Get-Partition -DriveLetter $letter | Get-Disk)
$external = $volume.DriveType -eq 'Removable' -or @($disks | Where-Object { $_.BusType -in @('USB', 'SD', 'MMC') }).Count -gt 0
if (-not $external) { throw 'Refusing an internal disk. Select the connected TF card volume.' }
$candidates = @((Join-Path $root 'uEnv.txt'), (Join-Path $root 'boot\uEnv.txt'))
$files = @($candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
if ($files.Count -ne 1) { throw 'Expected exactly one uEnv.txt on the TF boot volume; nothing was changed.' }
$path = $files[0]
if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'Refusing a linked boot configuration.'
}
[byte[]]$before = [IO.File]::ReadAllBytes($path)
if ($before.Length -gt 65536) { throw 'Unexpected uEnv.txt size; nothing was changed.' }
$change = Convert-MaixCamConsoleConfig -Bytes $before
$result = [ordered]@{ file = $path; activeConsoledevLines = $change.ChangedLines; applied = $false }
if ($Apply -and $change.ChangedLines -gt 0) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $backupDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) '.run\maixcam-recovery-20261027'
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    $hostBackup = Join-Path $backupDirectory ('uEnv-' + $stamp + '.txt')
    $cardBackup = $path + '.before-console-' + $stamp
    [IO.File]::WriteAllBytes($hostBackup, $before)
    [IO.File]::WriteAllBytes($cardBackup, $before)
    $expectedHash = (Get-FileHash -LiteralPath $hostBackup -Algorithm SHA256).Hash
    if ((Get-FileHash -LiteralPath $cardBackup -Algorithm SHA256).Hash -ne $expectedHash) {
        throw 'Backup verification failed; original configuration was not changed.'
    }
    $originalChanged = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $expectedHash
    if ($originalChanged) { throw 'Configuration changed during backup; original was not overwritten.' }
    try {
        [IO.File]::WriteAllBytes($path, $change.Bytes)
        [byte[]]$written = [IO.File]::ReadAllBytes($path)
        if ([Convert]::ToBase64String($written) -cne [Convert]::ToBase64String($change.Bytes)) {
            throw 'Boot configuration readback differs from the intended bytes.'
        }
        $verify = Convert-MaixCamConsoleConfig -Bytes $written
        if ($verify.ChangedLines -ne 0) { throw 'Console configuration verification failed.' }
    } catch {
        [IO.File]::WriteAllBytes($path, $before)
        throw
    }
    $result.applied = $true
    $result.hostBackup = $hostBackup
    $result.cardBackup = $cardBackup
    $result.beforeSha256 = $expectedHash
    $result.afterSha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}
$result | ConvertTo-Json
