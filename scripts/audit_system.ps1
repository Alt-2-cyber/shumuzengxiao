param(
    [string]$BackendUrl = "http://localhost:8080",
    [string]$FrontendUrl = "http://localhost:5173",
    [switch]$FailOnStaleHardware,
    [switch]$FailOnDiseaseDataNotReady
)

$ErrorActionPreference = "Stop"

function Check-Http($Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        return [pscustomobject]@{ ok = $true; status = $response.StatusCode; detail = $response.RawContentLength }
    } catch {
        return [pscustomobject]@{ ok = $false; status = 0; detail = $_.Exception.Message }
    }
}

function Read-Json($Url) {
    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec 8
    } catch {
        return $null
    }
}

function Read-FreshSnapshot($Url, [int]$TimeoutSeconds = 20) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $latest = $null
    do {
        $latest = Read-Json $Url
        if ($latest -and [bool]$latest.dataFresh) {
            return $latest
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    return $latest
}

$health = Check-Http "$BackendUrl/actuator/health"
$dashboard = Check-Http "$BackendUrl/api/dashboard"
$frontend = Check-Http $FrontendUrl
$snapshot = Read-FreshSnapshot "$BackendUrl/api/telemetry/snapshot?limit=1"
$models = Read-Json "$BackendUrl/api/models"
$ports = [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object

$diseaseData = @()
$python = "C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe"
$diseaseAudit = Join-Path $PSScriptRoot "audit_disease_data.py"
if ((Test-Path $python) -and (Test-Path $diseaseAudit)) {
    foreach ($family in @("vision", "audio", "lameness")) {
        try {
            $raw = (& $python $diseaseAudit --family $family 2>$null) -join [Environment]::NewLine
            $diseaseData += ($raw | ConvertFrom-Json)
        } catch {
            $diseaseData += [pscustomobject]@{
                scope = $family
                overallReady = $false
                error = $_.Exception.Message
            }
        }
    }
}

$firmwareFiles = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "..") -Recurse -File -Filter "firmware.bin" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "audio-training-data" })
function Find-Firmware($name, $pattern) {
    $item = $firmwareFiles | Where-Object { $_.FullName -match $pattern } | Select-Object -First 1
    [pscustomobject]@{ name = $name; exists = $null -ne $item; path = if ($item) { $item.FullName } else { $pattern } }
}
$firmware = @(
    (Find-Firmware "environment-esp32s3" "[\\/]\.pio[\\/]build[\\/]esp32s3[\\/]firmware\.bin$")
    (Find-Firmware "cow-esp32s3" "[\\/]\.pio[\\/]build[\\/]esp32s3_collar[\\/]firmware\.bin$")
    (Find-Firmware "demo-esp32" "[\\/]\.pio[\\/]build[\\/]demo_esp32[\\/]firmware\.bin$")
)

$dataFresh = [bool]($snapshot -and $snapshot.dataFresh)
$modelSummary = @($models | ForEach-Object {
    [pscustomobject]@{ name = $_.name; version = $_.version; status = $_.status; scope = $_.scope }
})

$report = [ordered]@{
    checkedAt = (Get-Date).ToUniversalTime().ToString("o")
    services = [ordered]@{
        mysqlPort = (Test-NetConnection -ComputerName "localhost" -Port 3306 -WarningAction SilentlyContinue).TcpTestSucceeded
        backendHealth = $health
        backendDashboard = $dashboard
        frontend = $frontend
    }
    hardware = [ordered]@{
        serialPortsPresent = @($ports)
        configuredPorts = @("COM5", "COM9")
        serialConnected = [bool]($snapshot -and $snapshot.serialConnected)
        dataFresh = $dataFresh
        status = if ($snapshot) { $snapshot.status } else { "unavailable" }
        lastReceivedAt = if ($snapshot) { $snapshot.lastReceivedAt } else { $null }
        lastError = if ($snapshot) { $snapshot.lastError } else { $null }
    }
    diseaseData = $diseaseData
    models = $modelSummary
    firmwareArtifacts = $firmware
}

$report | ConvertTo-Json -Depth 8

$firmwareComplete = @($firmware | Where-Object { -not $_.exists }).Count -eq 0
$criticalPass = $health.ok -and $dashboard.ok -and $frontend.ok -and
    $report.services.mysqlPort -and $firmwareComplete
if (-not $criticalPass) {
    exit 1
}
if ($FailOnStaleHardware -and -not $dataFresh) {
    exit 2
}
if ($FailOnDiseaseDataNotReady -and (@($diseaseData | Where-Object { -not $_.overallReady }).Count -gt 0)) {
    exit 3
}
