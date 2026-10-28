param(
    [ValidatePattern('^[A-Za-z]:[\\/]?$')][string]$DriveRoot = 'E:\',
    [Parameter(Mandatory)][string]$OutputDirectory,
    [ValidateSet('inspect', 'backup')][string]$Operation = 'inspect'
)

$ErrorActionPreference = 'Stop'
$letter = $DriveRoot.Substring(0, 1)
$root = $letter + ':\'
$disk = Get-Partition -DriveLetter $letter | Get-Disk
if ($disk.BusType -notin @('USB', 'SD', 'MMC')) { throw 'Refusing an internal disk.' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'uEnv.txt')) -or
    (Get-Content -LiteralPath (Join-Path $root 'board') -Raw) -notmatch '(?m)^id=maixcam\r?$' -or
    (Get-Content -LiteralPath (Join-Path $root 'ver') -Raw) -notmatch '^maixcam-') {
    throw 'The selected volume is not the expected MaixCAM boot partition.'
}
$partitions = @(Get-Partition -DiskNumber $disk.Number | Where-Object { $_.PartitionNumber -eq 2 })
if ($partitions.Count -ne 1) { throw 'Expected one Linux partition2; nothing was changed.' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$descriptor = [ordered]@{
    disk_number = [int]$disk.Number
    disk_size = [long]$disk.Size
    bus_type = [string]$disk.BusType
    partition_offset = [long]$partitions[0].Offset
    partition_size = [long]$partitions[0].Size
    maixcam_boot_verified = $true
    boot_version = (Get-Content -LiteralPath (Join-Path $root 'ver') -Raw).Trim()
    read_only = $true
}
$descriptorPath = Join-Path $OutputDirectory 'card-descriptor.json'
$descriptor | ConvertTo-Json | Set-Content -LiteralPath $descriptorPath -Encoding UTF8
$python = 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe'
$scriptName = if ($Operation -eq 'backup') { 'maixcam_partition_backup.py' } else { 'maixcam_offline_inspect.py' }
$script = Join-Path $PSScriptRoot $scriptName
& $python -u $script --descriptor $descriptorPath --output $OutputDirectory `
    1> (Join-Path $OutputDirectory 'inspector.stdout.log') `
    2> (Join-Path $OutputDirectory 'inspector.stderr.log')
exit $LASTEXITCODE
