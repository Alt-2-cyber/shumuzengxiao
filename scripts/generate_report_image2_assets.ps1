$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
  throw "Set OPENAI_API_KEY in the process environment before running this script."
}
$outDir = "D:\table\shumuzengxiao\report_assets"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$jobs = @(
  @{
    file = "image2-hardware-deployment.png"
    prompt = "Professional realistic technical report illustration, smart cattle barn hardware deployment: ESP32-S3 sensor control box, air quality sensors, fan actuator, relay cabinet, cable routing, cattle barn background, clean installation, agricultural IoT edge device, no text, no logos, no watermark."
  },
  @{
    file = "image2-edge-vision-ai.png"
    prompt = "Professional realistic technical report illustration, edge AI camera observing cattle in a barn, subtle bounding boxes and posture detection overlays without readable text, MaixCam-like compact camera, local AI inference concept, no text, no logos, no watermark."
  },
  @{
    file = "image2-audio-environment-fusion.png"
    prompt = "High quality conceptual technical illustration, multimodal cattle health monitoring: sound waves from barn microphone, air quality particles, temperature humidity sensors, cattle silhouettes, data streams merging into an AI analytics node, no text, no logos, no watermark."
  },
  @{
    file = "image2-mobile-field-inspection.png"
    prompt = "Realistic field inspection scene: farm worker holding a smartphone app near cattle, taking a close-up photo for AI health inspection, modern but practical cattle barn, soft natural light, no text on screen, no logos, no watermark."
  },
  @{
    file = "image2-cloud-dashboard-ops.png"
    prompt = "Professional technology report illustration, cloud dashboard operations center for smart livestock monitoring, large screens with abstract charts and barn telemetry visuals, edge-to-cloud data streams, no readable text, no logos, no watermark."
  },
  @{
    file = "image2-maintenance-testing.png"
    prompt = "Realistic technical maintenance scene, engineer testing smart barn sensor node with multimeter and laptop, ESP32 development board, relays, DC-DC power module, organized workbench inside agricultural facility, no text, no logos, no watermark."
  }
)

foreach ($job in $jobs) {
  $target = Join-Path $outDir $job.file
  if (Test-Path $target) {
    Write-Output "exists=$target"
    continue
  }
  $body = @{
    model = "gpt-image-2"
    prompt = $job.prompt
    size = "1536x1024"
    quality = "medium"
    n = 1
  } | ConvertTo-Json -Depth 5

  try {
    $res = Invoke-RestMethod -Uri "https://www.easynet.cc/v1/images/generations" `
      -Method Post `
      -Headers @{ Authorization = "Bearer $env:OPENAI_API_KEY"; "Content-Type" = "application/json" } `
      -Body $body `
      -TimeoutSec 240

    $b64 = $res.data[0].b64_json
    if ($b64) {
      [IO.File]::WriteAllBytes($target, [Convert]::FromBase64String($b64))
    } elseif ($res.data[0].url) {
      $img = Invoke-WebRequest -Uri $res.data[0].url -UseBasicParsing -TimeoutSec 120
      [IO.File]::WriteAllBytes($target, $img.Content)
    } else {
      throw "No b64_json or url in response."
    }
    Write-Output "generated=$target"
  } catch {
    Write-Output ("failed=" + $job.file + " :: " + $_.Exception.Message)
  }
}
