$ErrorActionPreference = 'Stop'
$root = 'D:\table\软著申请\牛'
$qa = 'D:\table\shumuzengxiao\.run\application-form-fill-20261024\rendered'
New-Item -ItemType Directory -Path $qa -Force | Out-Null
$word = $null
$results = @()
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    Get-ChildItem -LiteralPath $root -Directory | Where-Object { $_.Name -like '数牧增效*' } | ForEach-Object {
        $file = Join-Path $_.FullName '申请表模板-待本人填写.docx'
        $doc = $null
        try {
            $doc = $word.Documents.Open($file)
            [void]$doc.Fields.Update()
            $doc.Repaginate()
            $pdf = Join-Path $qa ($_.Name + '-申请表.pdf')
            $doc.ExportAsFixedFormat($pdf, 17)
            $results += [PSCustomObject]@{ Software = $_.Name; Pages = $doc.ComputeStatistics(2); Pdf = $pdf; Characters = $doc.Content.Text.Length }
        } finally {
            if ($null -ne $doc) {
                $doc.Close()
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
            }
        }
    }
    $results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $qa 'export.json') -Encoding utf8
    $results | ConvertTo-Json -Compress | Write-Output
} finally {
    if ($null -ne $word) {
        $word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
}
