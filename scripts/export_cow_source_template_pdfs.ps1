$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\table\shumuzengxiao\.run\source-template-format-20261023'
$manifest = Get-Content -LiteralPath (Join-Path $taskRoot '待检查清单.json') -Raw -Encoding utf8 | ConvertFrom-Json
$filePaths = @((Join-Path $taskRoot '参考代码模板.docx')) + @($manifest | ForEach-Object { $_.staged })
$wordInstance = $null
$results = @()
try {
    $wordInstance = New-Object -ComObject Word.Application
    $wordInstance.Visible = $false
    $wordInstance.DisplayAlerts = 0
    $wordInstance.AutomationSecurity = 3
    foreach ($filePath in $filePaths) {
        $document = $null
        try {
            $document = $wordInstance.Documents.Open($filePath)
            [void]$document.Fields.Update()
            $document.Repaginate()
            $pdfPath = [System.IO.Path]::ChangeExtension($filePath, '.pdf')
            if (-not $document.ReadOnly) { $document.Save() }
            $document.ExportAsFixedFormat($pdfPath, 17)
            $item = [PSCustomObject]@{ Name = [System.IO.Path]::GetFileName($filePath); Pages = $document.ComputeStatistics(2); Pdf = $pdfPath }
            $results += $item
            $item | ConvertTo-Json -Compress | Write-Output
        } finally {
            if ($null -ne $document) {
                $document.Close()
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
            }
        }
    }
    $results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskRoot 'Word分页检查.json') -Encoding utf8
} finally {
    if ($null -ne $wordInstance) {
        $wordInstance.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordInstance)
    }
}
