param(
    [Parameter(Mandatory)][string]$DescriptorPath,
    [Parameter(Mandatory)][string]$BackupSummary,
    [Parameter(Mandatory)][string]$PlanPath,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [switch]$UseVolumeLock
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
$wasOffline = [bool]$disk.IsOffline
$volumeArgs = @()
if ($UseVolumeLock) {
    if ($wasOffline) { throw 'Volume locking requires the removable camera disk to be online.' }
    $bootPartition = Get-Partition -DiskNumber $disk.Number -PartitionNumber 1
    $volumePaths = @($bootPartition.AccessPaths | Where-Object { $_ -like '\\?\Volume{*}\' })
    if ($volumePaths.Count -ne 1 -or $bootPartition.Offset -lt 512 -or
        $bootPartition.Offset + $bootPartition.Size -gt $partition.Offset) {
        throw 'The camera boot volume identity is not available for locking.'
    }
    $volumeArgs = @('--boot-volume', $volumePaths[0].TrimEnd([char]'\'))
} elseif (-not $disk.IsOffline) {
    Set-Disk -Number $disk.Number -IsOffline $true
}
$python = 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe'
$script = Join-Path $PSScriptRoot 'maixcam_apply_card_patch.py'
$applyCode = 1
try {
    & $python -u $script --descriptor $DescriptorPath --backup-summary $BackupSummary --plan $PlanPath `
        --output $OutputDirectory --apply @volumeArgs `
        1> (Join-Path $OutputDirectory 'apply.stdout.log') `
        2> (Join-Path $OutputDirectory 'apply.stderr.log')
    $applyCode = $LASTEXITCODE
} finally {
    $resultPath = Join-Path $OutputDirectory 'apply-result.json'
    $verifiedSuccess = $false
    if ($applyCode -eq 0 -and (Test-Path -LiteralPath $resultPath)) {
        $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
        $verifiedSuccess = $result.phase -eq 'complete' -and $result.startup_files_verified
    }
    if ($verifiedSuccess -and -not $wasOffline -and -not $UseVolumeLock) {
        $currentDisk = Get-Disk -Number $disk.Number
        if ($currentDisk.UniqueId -ne $disk.UniqueId -or $currentDisk.Size -ne $disk.Size -or
            $currentDisk.BusType -ne $disk.BusType -or $currentDisk.SerialNumber -ne $disk.SerialNumber) {
            throw 'Camera disk identity changed; refusing to bring a different disk online.'
        }
        Set-Disk -Number $disk.Number -IsOffline $false
    } elseif (-not $verifiedSuccess) {
        if ($UseVolumeLock) {
            Write-Warning 'Patch did not complete verification. Do not boot the camera; inspect the rollback result.'
        } else {
            Write-Warning 'Patch did not complete verification. The camera disk remains offline for inspection.'
        }
    }
}
exit $applyCode
