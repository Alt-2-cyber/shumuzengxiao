param(
    [ValidateSet("all", "backend", "frontend")]
    [string]$Service = "all",

    [ValidateSet("mysql", "default")]
    [string]$Profile = "mysql",

    [switch]$Rebuild,

    [switch]$SkipDatabaseMigration,

    [switch]$EnableSerial
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "smart-cattle-backend"
$FrontendDir = Join-Path $Root "smart-cattle-frontend"
$LogsDir = Join-Path $Root "logs"
$RunDir = Join-Path $Root ".run"
$BackendJar = Join-Path $BackendDir "target\smart-cattle-backend-0.1.0.jar"
$MySqlMigration = Join-Path $Root "database\migrate_existing_mysql.sql"

New-Item -ItemType Directory -Force -Path $LogsDir, $RunDir | Out-Null

function Write-Step($Message) {
    Write-Host "[smart-cattle] $Message"
}

function Get-PortOwner($Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) {
        return $null
    }

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
    [pscustomobject]@{
        Port = $Port
        ProcessId = $conn.OwningProcess
        Name = $proc.Name
        CommandLine = $proc.CommandLine
    }
}

function Test-OwnProcess($Owner, [string[]]$ExpectedMarkers) {
    if (-not $Owner -or -not $Owner.CommandLine) {
        return $false
    }
    $commandLine = $Owner.CommandLine.ToLowerInvariant()
    foreach ($marker in $ExpectedMarkers) {
        if ($marker -and $commandLine.Contains($marker.ToLowerInvariant())) {
            return $true
        }
    }
    return $false
}

function Wait-Port($Port, $TimeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Get-PortOwner $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Get-MySqlClient {
    if ($env:SMART_CATTLE_MYSQL_CLIENT -and (Test-Path $env:SMART_CATTLE_MYSQL_CLIENT)) {
        return (Resolve-Path $env:SMART_CATTLE_MYSQL_CLIENT).Path
    }
    $command = Get-Command mysql.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }
    return $null
}

function Invoke-MySqlMigration {
    if ($Profile -ne "mysql" -or $SkipDatabaseMigration) {
        return
    }
    if (-not (Test-Path $MySqlMigration)) {
        throw "MySQL migration script is missing: $MySqlMigration"
    }

    $mysql = Get-MySqlClient
    if (-not $mysql) {
        throw "MySQL profile needs mysql.exe to apply database migrations. Add mysql.exe to PATH or set SMART_CATTLE_MYSQL_CLIENT."
    }

    $hostName = if ($env:SMART_CATTLE_MYSQL_HOST) { $env:SMART_CATTLE_MYSQL_HOST } else { "127.0.0.1" }
    $port = if ($env:SMART_CATTLE_MYSQL_PORT) { $env:SMART_CATTLE_MYSQL_PORT } else { "3306" }
    $database = if ($env:SMART_CATTLE_MYSQL_DATABASE) { $env:SMART_CATTLE_MYSQL_DATABASE } else { "smart_cattle" }
    $user = if ($env:SMART_CATTLE_MYSQL_USER) { $env:SMART_CATTLE_MYSQL_USER } else { "root" }
    $password = if ($null -ne $env:SMART_CATTLE_MYSQL_PASSWORD) { $env:SMART_CATTLE_MYSQL_PASSWORD } else { "root" }
    $hadPassword = Test-Path Env:MYSQL_PWD
    $previousPassword = $env:MYSQL_PWD

    Write-Step "Applying MySQL schema migration..."
    try {
        $env:MYSQL_PWD = $password
        Get-Content -Raw -Encoding UTF8 $MySqlMigration |
            & $mysql -h $hostName -P $port -u $user -D $database --default-character-set=utf8mb4 |
            Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "MySQL migration failed with exit code $LASTEXITCODE. Verify SMART_CATTLE_MYSQL_* settings and the database service."
        }
    } finally {
        if ($hadPassword) {
            $env:MYSQL_PWD = $previousPassword
        } else {
            Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
        }
    }
}

function Ensure-BackendJar {
    $jarOutdated = -not (Test-Path $BackendJar)
    if (-not $jarOutdated) {
        $jarTime = (Get-Item $BackendJar).LastWriteTimeUtc
        $sourceFiles = Get-ChildItem (Join-Path $BackendDir "src") -File -Recurse
        $jarOutdated = @($sourceFiles | Where-Object {
            $_.LastWriteTimeUtc -gt $jarTime
        }).Count -gt 0
    }

    if ($Rebuild -or $jarOutdated) {
        Write-Step "Building backend jar..."
        Push-Location $BackendDir
        try {
            & mvn package -DskipTests
            if ($LASTEXITCODE -ne 0) {
                throw "Backend build failed with exit code $LASTEXITCODE"
            }
        } finally {
            Pop-Location
        }
    }
}

function Ensure-FrontendDeps {
    $nodeModules = Join-Path $FrontendDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Step "Installing frontend dependencies..."
        Push-Location $FrontendDir
        try {
            & npm install
            if ($LASTEXITCODE -ne 0) {
                throw "npm install failed with exit code $LASTEXITCODE"
            }
        } finally {
            Pop-Location
        }
    }
}

function Start-Backend {
    $owner = Get-PortOwner 8080
    if ($owner) {
        if (Test-OwnProcess $owner @($BackendDir, "smart-cattle-backend-0.1.0.jar")) {
            Write-Step "Backend already running on http://localhost:8080 (PID $($owner.ProcessId))."
            return
        }
        throw "Port 8080 is occupied by PID $($owner.ProcessId): $($owner.CommandLine)"
    }

    Invoke-MySqlMigration
    Ensure-BackendJar

    # Windows DPAPI keeps the local provider key outside source files and client bundles.
    $assistantSecret = Join-Path $RunDir "cattle-assistant-key.clixml"
    if (-not $env:CATTLE_ASSISTANT_API_KEY -and (Test-Path -LiteralPath $assistantSecret)) {
        $secureKey = Import-Clixml -LiteralPath $assistantSecret
        $env:CATTLE_ASSISTANT_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
        if (-not $env:CATTLE_ASSISTANT_ENDPOINT) {
            $env:CATTLE_ASSISTANT_ENDPOINT = "https://api.deepseek.com/chat/completions"
        }
        if (-not $env:CATTLE_ASSISTANT_MODEL) {
            $env:CATTLE_ASSISTANT_MODEL = "deepseek-chat"
        }
    }

    $args = @("-jar", "target\smart-cattle-backend-0.1.0.jar")
    if ($Profile -eq "mysql") {
        $args += "--spring.profiles.active=mysql"
    }

    Write-Step "Starting backend with profile '$Profile'..."
    $process = Start-Process `
        -FilePath "java" `
        -ArgumentList $args `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput (Join-Path $LogsDir "backend.log") `
        -RedirectStandardError (Join-Path $LogsDir "backend.err.log") `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path (Join-Path $RunDir "backend.pid") -Value $process.Id -Encoding ASCII

    if (-not (Wait-Port 8080 40)) {
        throw "Backend did not start on port 8080. Check logs\backend.err.log and logs\backend.log."
    }
    Write-Step "Backend ready: http://localhost:8080/api/dashboard"
}

function Start-Frontend {
    $owner = Get-PortOwner 5173
    if ($owner) {
        if (Test-OwnProcess $owner @($FrontendDir, "vite --host")) {
            Write-Step "Frontend already running on http://localhost:5173 (PID $($owner.ProcessId))."
            return
        }
        throw "Port 5173 is occupied by PID $($owner.ProcessId): $($owner.CommandLine)"
    }

    Ensure-FrontendDeps

    Write-Step "Starting frontend dev server..."
    $process = Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory $FrontendDir `
        -RedirectStandardOutput (Join-Path $LogsDir "frontend.log") `
        -RedirectStandardError (Join-Path $LogsDir "frontend.err.log") `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path (Join-Path $RunDir "frontend.pid") -Value $process.Id -Encoding ASCII

    if (-not (Wait-Port 5173 30)) {
        throw "Frontend did not start on port 5173. Check logs\frontend.err.log and logs\frontend.log."
    }
    Write-Step "Frontend ready: http://localhost:5173"
}

Write-Step "Workspace: $Root"

if ($EnableSerial) {
    $env:ESP32_SERIAL_ENABLED = "true"
    if (-not $env:ESP32_SERIAL_PORTS) {
        $env:ESP32_SERIAL_PORTS = "COM5,COM9"
    }
    if (-not $env:ESP32_COW_SERIAL_PORT) {
        $env:ESP32_COW_SERIAL_PORT = "COM9"
    }
    if (-not $env:ESP32_ENV_SERIAL_PORT) {
        $env:ESP32_ENV_SERIAL_PORT = "COM5"
    }
    # A Bluetooth service may have the same COM alias as an ESP32 USB interface.
    foreach ($node in @(@{ Port = $env:ESP32_ENV_SERIAL_PORT; Key = 'ESP32_ENV_SERIAL_SYSTEM_PATH' },
                         @{ Port = $env:ESP32_COW_SERIAL_PORT; Key = 'ESP32_COW_SERIAL_SYSTEM_PATH' })) {
        if (-not [Environment]::GetEnvironmentVariable($node.Key, 'Process')) {
            $usbPort = Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
                Where-Object { $_.InstanceId -like 'USB\*' -and $_.FriendlyName -match ('\(' + [regex]::Escape($node.Port) + '\)$') } |
                Select-Object -First 1
            if ($usbPort) {
                $systemPath = '\\?\' + ($usbPort.InstanceId -replace '\\', '#') + '#{86e0d1e0-8089-11d0-9ce4-08003e301f73}'
                [Environment]::SetEnvironmentVariable($node.Key, $systemPath, 'Process')
            }
        }
    }
    Write-Step "Serial telemetry enabled: $($env:ESP32_SERIAL_PORTS)"
}

if ($Service -eq "all" -or $Service -eq "backend") {
    Start-Backend
}

if ($Service -eq "all" -or $Service -eq "frontend") {
    Start-Frontend
}

Write-Step "Done."
Write-Host ""
Write-Host "Open frontend: http://localhost:5173"
Write-Host "Backend API:   http://localhost:8080/api/dashboard"
