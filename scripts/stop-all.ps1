$ErrorActionPreference = "Continue"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RunDir = Join-Path $Root ".run"
$BackendDir = Join-Path $Root "smart-cattle-backend"
$FrontendDir = Join-Path $Root "smart-cattle-frontend"

function Write-Step($Message) {
    Write-Host "[smart-cattle] $Message"
}

function Test-OwnCommandLine($CommandLine, [string[]]$ExpectedMarkers) {
    if (-not $CommandLine) {
        return $false
    }
    $lower = $CommandLine.ToLowerInvariant()
    foreach ($marker in $ExpectedMarkers) {
        if ($marker -and $lower.Contains($marker.ToLowerInvariant())) {
            return $true
        }
    }
    return $false
}

function Stop-ByPidFile($FileName, [string[]]$ExpectedMarkers) {
    $path = Join-Path $RunDir $FileName
    if (-not (Test-Path $path)) {
        return
    }

    $pidValue = (Get-Content $path -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $pidValue) {
        return
    }

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue" -ErrorAction SilentlyContinue
    if ($proc -and (Test-OwnCommandLine $proc.CommandLine $ExpectedMarkers)) {
        Write-Step "Stopping PID $pidValue..."
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $path -Force -ErrorAction SilentlyContinue
}

function Stop-ProjectPort($Port, [string[]]$ExpectedMarkers) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
        if ($proc -and (Test-OwnCommandLine $proc.CommandLine $ExpectedMarkers)) {
            Write-Step "Stopping port $Port PID $($conn.OwningProcess)..."
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Stop-ByPidFile "backend.pid" @($BackendDir, "smart-cattle-backend-0.1.0.jar")
Stop-ByPidFile "frontend.pid" @($FrontendDir, "vite --host")
Stop-ProjectPort 8080 @($BackendDir, "smart-cattle-backend-0.1.0.jar")
Stop-ProjectPort 5173 @($FrontendDir, "vite --host")

Write-Step "Stopped project services."
