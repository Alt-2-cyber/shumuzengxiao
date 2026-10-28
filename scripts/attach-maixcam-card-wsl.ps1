param(
    [ValidatePattern('^[A-Za-z]:[\\/]?$')][string]$DriveRoot = 'E:\',
    [Parameter(Mandatory)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$letter = $DriveRoot.Substring(0, 1)
$root = $letter + ':\'
$disk = Get-Partition -DriveLetter $letter | Get-Disk
if ($disk.BusType -notin @('USB', 'SD', 'MMC')) { throw 'Refusing an internal disk.' }
if ((Get-Content -LiteralPath (Join-Path $root 'board') -Raw) -notmatch '(?m)^id=maixcam\r?$') {
    throw 'Expected the verified MaixCAM boot volume.'
}
$partition = @(Get-Partition -DiskNumber $disk.Number | Where-Object { $_.PartitionNumber -eq 2 })
if ($partition.Count -ne 1) { throw 'Expected exactly one Linux partition2.' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$descriptor = [ordered]@{
    disk_number = [int]$disk.Number
    disk_size = [long]$disk.Size
    bus_type = [string]$disk.BusType
    partition_offset = [long]$partition[0].Offset
    partition_size = [long]$partition[0].Size
    maixcam_boot_verified = $true
    boot_version = (Get-Content -LiteralPath (Join-Path $root 'ver') -Raw).Trim()
    volume_path = [string](Get-Volume -DriveLetter $letter).Path
}
$descriptor | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'card-descriptor.json') -Encoding UTF8
$devicePath = '\\.\PHYSICALDRIVE' + $disk.Number
& wsl.exe --mount $devicePath --bare `
    1> (Join-Path $OutputDirectory 'wsl-attach.stdout.log') `
    2> (Join-Path $OutputDirectory 'wsl-attach.stderr.log')
$attachCode = $LASTEXITCODE
[pscustomobject]@{ Attached = ($attachCode -eq 0); ExitCode = $attachCode; Device = $devicePath } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'attach-result.json') -Encoding UTF8
exit $attachCode
