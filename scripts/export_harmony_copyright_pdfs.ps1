param(
    [Parameter(Mandatory = $true)][string]$MaterialFolder,
    [Parameter(Mandatory = $true)][string]$ReportPath
)

$ErrorActionPreference = 'Stop'
$wordInstance = $null
$results = @()
try {
    $wordInstance = New-Object -ComObject Word.Application
    $wordInstance.Visible = $false
    $wordInstance.DisplayAlerts = 0
    $wordInstance.AutomationSecurity = 3
    $files = Get-ChildItem -LiteralPath $MaterialFolder -File -Filter '*.docx' |
        Where-Object { $_.Name -notlike '申请表模板*' -and $_.Name -notlike '~$*' }
    foreach ($file in $files) {
        $document = $null
        try {
            $document = $wordInstance.Documents.Open($file.FullName)
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
    $results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding utf8
} finally {
    if ($null -ne $wordInstance) {
        $wordInstance.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordInstance)
    }
}
