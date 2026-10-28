param(
    [string]$HostName = "10.131.167.1",
    [string]$User = "root",
    [string]$RemoteRoot = "/root/cattle-vision",
    [string]$BackendUrl = "",
    [switch]$StartNode
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SourceRoot = Join-Path $ProjectRoot '硬件代码\MaixCam节点'
if (-not $SourceRoot) {
    throw "Cannot find the MaixCam directory under the hardware project."
}
$ModelRoot = Join-Path $SourceRoot "models"
if ($RemoteRoot -notmatch '^/root/[A-Za-z0-9_-]+$') {
    throw 'RemoteRoot must be a single project directory under /root.'
}
if ($BackendUrl -and $BackendUrl -notmatch '^https?://[A-Za-z0-9.:-]+/?$') {
    throw 'BackendUrl must be an HTTP(S) origin.'
}

if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
    throw "OpenSSH ssh.exe is required."
}
if (-not (Get-Command scp.exe -ErrorAction SilentlyContinue)) {
    throw "OpenSSH scp.exe is required."
}

$required = @(
    (Join-Path $SourceRoot "main.py"),
    (Join-Path $SourceRoot "config.json"),
    (Join-Path $SourceRoot "manage_node.py"),
    (Join-Path $ModelRoot "cattle_yolov8.mud"),
    (Join-Path $ModelRoot "cattle_yolov8.cvimodel")
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required deployment file is missing: $path"
    }
}

$destination = "$User@$HostName"
Write-Host "Deploying MaixCam node to $destination`:$RemoteRoot"
Write-Host "SSH will ask for the device password interactively."

& ssh.exe $destination "mkdir -p '$RemoteRoot/models' '$RemoteRoot/logs'; if [ -f '$RemoteRoot/manage_node.py' ]; then python3 '$RemoteRoot/manage_node.py' stop; fi"
if ($LASTEXITCODE -ne 0) { throw "Cannot create remote MaixCam directories." }

$uploadFiles = @(
    (Join-Path $SourceRoot 'main.py'),
    (Join-Path $SourceRoot 'manage_node.py'),
    (Join-Path $ModelRoot 'cattle_yolov8.mud'),
    (Join-Path $ModelRoot 'cattle_yolov8.cvimodel')
)
& scp.exe @uploadFiles "$destination`:$RemoteRoot/"
if ($LASTEXITCODE -ne 0) { throw "MaixCam file upload failed." }
& scp.exe (Join-Path $SourceRoot 'config.json') "$destination`:$RemoteRoot/config.default.json"
if ($LASTEXITCODE -ne 0) { throw 'MaixCam configuration template upload failed.' }

& ssh.exe $destination "cp '$RemoteRoot/cattle_yolov8.mud' '$RemoteRoot/models/cattle_yolov8.mud'; cp '$RemoteRoot/cattle_yolov8.cvimodel' '$RemoteRoot/models/cattle_yolov8.cvimodel'; python3 '$RemoteRoot/manage_node.py' configure $(if ($BackendUrl) { "--backend-url '$BackendUrl'" })"
if ($LASTEXITCODE -ne 0) { throw 'MaixCam configuration failed.' }
if ($StartNode) {
    & ssh.exe $destination "python3 '$RemoteRoot/manage_node.py' start"
    if ($LASTEXITCODE -ne 0) { throw 'MaixCam project start failed; inspect its log.' }
}

Write-Host "Project files installed. Use -StartNode after checking the system camera is free; verify $RemoteRoot/logs/vision.log."
