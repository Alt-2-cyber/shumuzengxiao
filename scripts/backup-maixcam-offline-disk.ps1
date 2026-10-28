param(
    [Parameter(Mandatory)][string]$DescriptorPath,
    [Parameter(Mandatory)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$descriptor = Get-Content -LiteralPath $DescriptorPath -Raw | ConvertFrom-Json
$disk = Get-Disk -Number ([int]$descriptor.disk_number)
if ($disk.BusType -notin @('USB', 'SD', 'MMC') -or $disk.Size -ne [long]$descriptor.disk_size -or
    -not $descriptor.maixcam_boot_verified) { throw 'The external camera disk identity changed.' }
$partition = Get-Partition -DiskNumber $disk.Number -PartitionNumber 2
if ($partition.Offset -ne [long]$descriptor.partition_offset -or $partition.Size -ne [long]$descriptor.partition_size) {
    throw 'The camera partition layout changed.'
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$python = 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe'
$script = Join-Path $PSScriptRoot 'maixcam_partition_backup.py'
& $python -u $script --descriptor $DescriptorPath --output $OutputDirectory `
    1> (Join-Path $OutputDirectory 'backup.stdout.log') `
    2> (Join-Path $OutputDirectory 'backup.stderr.log')
exit $LASTEXITCODE
