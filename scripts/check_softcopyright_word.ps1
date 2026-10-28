$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$materialRoot = Join-Path $projectRoot '软著材料'
$reviewRoot = Join-Path $projectRoot '.run\softcopyright-word-check'
New-Item -ItemType Directory -Force -Path $reviewRoot | Out-Null
$wordCheck = $null
try {
    $wordCheck = New-Object -ComObject Word.Application
    $wordCheck.Visible = $false
    $wordCheck.DisplayAlerts = 0
    $wordCheck.AutomationSecurity = 3
    $documents = Get-ChildItem -LiteralPath $materialRoot -File -Filter '*.docx'
    foreach ($file in $documents) {
        $wordDocument = $null
        try {
            $wordDocument = $wordCheck.Documents.Open($file.FullName)
            $wordDocument.Repaginate()
            $pageCount = $wordDocument.ComputeStatistics(2)
            $textCount = $wordDocument.Content.Text.Length
            $pdfName = if ($file.Name -like '*程序鉴别材料*') { 'program-word.pdf' } else { 'design-word.pdf' }
            $pdfPath = Join-Path $reviewRoot $pdfName
            $wordDocument.ExportAsFixedFormat($pdfPath, 17)
            [PSCustomObject]@{
                Name = $file.Name
                Pages = $pageCount
                EditableCharacters = $textCount
                ReviewPdf = $pdfPath
            } | ConvertTo-Json -Compress
        } finally {
            if ($null -ne $wordDocument) {
                $wordDocument.Close()
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDocument)
            }
        }
    }
} finally {
    if ($null -ne $wordCheck) {
        $wordCheck.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordCheck)
    }
}
