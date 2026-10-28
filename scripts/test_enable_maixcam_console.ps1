$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'enable-maixcam-console.ps1')

$utf8 = [Text.UTF8Encoding]::new($false)
function Check-Config {
    param([string]$Before, [string]$After, [int]$Changes)
    $result = Convert-MaixCamConsoleConfig -Bytes $utf8.GetBytes($Before)
    if ($utf8.GetString($result.Bytes) -cne $After -or $result.ChangedLines -ne $Changes) {
        throw 'Console configuration transformation did not preserve expected content.'
    }
}

Check-Config "consoledev=null`nroot=/dev/mmcblk0p2`n" "# consoledev=null`nroot=/dev/mmcblk0p2`n" 1
Check-Config "# consoledev=null`nroot=/dev/mmcblk0p2" "# consoledev=null`nroot=/dev/mmcblk0p2" 0
Check-Config "bootargs=x`r`n  consoledev = null`r`nconsoledev_extra=x`r`n" "bootargs=x`r`n  # consoledev = null`r`nconsoledev_extra=x`r`n" 1
Check-Config "consoledev=null" "# consoledev=null" 1
$bom = [byte[]](@(239, 187, 191) + $utf8.GetBytes("consoledev=null`r`n"))
$result = Convert-MaixCamConsoleConfig -Bytes $bom
if ($result.Bytes[0] -ne 239 -or $result.Bytes[1] -ne 187 -or $result.Bytes[2] -ne 191 -or $result.ChangedLines -ne 1) {
    throw 'UTF-8 BOM was not preserved.'
}
$rejected = $false
try { Convert-MaixCamConsoleConfig -Bytes ([byte[]]@(99, 0, 100)) | Out-Null } catch { $rejected = $true }
if (-not $rejected) { throw 'Binary boot configuration was not rejected.' }
Write-Output '6 boot configuration checks passed. No disk or camera was changed.'
