$ErrorActionPreference = 'Stop'
$materialRoot = 'D:\table\软著申请\牛'
$wordInstance = $null
$results = @()
try {
    $wordInstance = New-Object -ComObject Word.Application
    $wordInstance.Visible = $false
    $wordInstance.DisplayAlerts = 0
    $wordInstance.AutomationSecurity = 3
    $folders = Get-ChildItem -LiteralPath $materialRoot -Directory |
        Where-Object { $_.Name -like '数牧增效*' }
    foreach ($folder in $folders) {
        $files = Get-ChildItem -LiteralPath $folder.FullName -File -Filter '*.docx' |
            Where-Object { $_.Name -notlike '申请表模板*' }
        foreach ($file in $files) {
            $document = $null
            try {
                $document = $wordInstance.Documents.Open($file.FullName)
                $document.Repaginate()
                [void]$document.Fields.Update()
                foreach ($section in $document.Sections) {
                    [void]$section.Footers.Item(1).Range.Fields.Update()
                }
                $document.Repaginate()
                $count = $document.ComputeStatistics(2)
                $pdfPath = [System.IO.Path]::ChangeExtension($file.FullName, '.pdf')
                $document.Save()
                $document.ExportAsFixedFormat($pdfPath, 17)
                $item = [PSCustomObject]@{
                    Software = $folder.Name
                    Name = $file.Name
                    Pages = $count
                    Characters = $document.Content.Text.Length
                    Pdf = $pdfPath
                    PdfBytes = (Get-Item -LiteralPath $pdfPath).Length
                }
                $results += $item
                $item | ConvertTo-Json -Compress | Write-Output
            } finally {
                if ($null -ne $document) {
                    $document.Close()
                    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
                }
            }
        }
    }
    $results | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath (Join-Path $materialRoot 'Word分页与PDF导出检查.json') -Encoding utf8
} finally {
    if ($null -ne $wordInstance) {
        $wordInstance.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordInstance)
    }
}
