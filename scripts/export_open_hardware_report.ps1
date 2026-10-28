param(
    [string]$ReportDirectory = 'D:\table\shumuzengxiao\outputs\open_hardware_submission_20261026'
)

$ErrorActionPreference = 'Stop'
$reportRoot = (Resolve-Path -LiteralPath $ReportDirectory).Path
$reportFile = Get-ChildItem -LiteralPath $reportRoot -Filter '*.docx' | Select-Object -First 1
if (-not $reportFile) { throw 'No report DOCX found.' }
$pdfPath = [System.IO.Path]::ChangeExtension($reportFile.FullName, '.pdf')
$word = $null
$document = $null
$ownsWord = $false
$previousAlerts = $null
$previousAutomationSecurity = $null
try {
    try {
        $word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')
    }
    catch {
        $word = New-Object -ComObject Word.Application
        $ownsWord = $true
        $word.Visible = $false
    }
    $previousAlerts = $word.DisplayAlerts
    $previousAutomationSecurity = $word.AutomationSecurity
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($reportFile.FullName, $false, $false)
    $document.UpdateStylesOnOpen = $false
    $document.Styles.Item(-63).Borders.Enable = 0
    $document.Styles.Item(-63).Font.Color = 0
    $document.Styles.Item(-75).Font.Italic = 0
    $document.Styles.Item(-75).Font.Color = 0
    $null = $document.Fields.Update()
    foreach ($toc in $document.TablesOfContents) {
        $toc.Update()
        $toc.Range.Font.Size = 10.5
        $toc.Range.Font.NameFarEast = 'Microsoft YaHei'
        $toc.Range.Font.Color = 0
        $toc.Range.ParagraphFormat.SpaceBefore = 0
        $toc.Range.ParagraphFormat.SpaceAfter = 2
        $toc.Range.ParagraphFormat.LineSpacingRule = 4
        $toc.Range.ParagraphFormat.LineSpacing = 15
        $toc.Range.ParagraphFormat.KeepWithNext = 0
    }
    $document.Repaginate()
    foreach ($toc in $document.TablesOfContents) { $toc.UpdatePageNumbers() }
    $document.Save()
    $document.ExportAsFixedFormat($pdfPath, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1)
    $info = [ordered]@{
        renderer = 'Microsoft Word desktop PDF export'
        docx = $reportFile.FullName
        pdf = $pdfPath
        pages = $document.ComputeStatistics(2)
        tables = $document.Tables.Count
        tocEntries = $document.TablesOfContents.Count
    }
    $info | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'work\word-export.json') -Encoding utf8
    $info | ConvertTo-Json
}
finally {
    if ($document) {
        $document.Close(0)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($word) {
        if ($ownsWord) {
            $word.Quit()
        }
        else {
            $word.DisplayAlerts = $previousAlerts
            $word.AutomationSecurity = $previousAutomationSecurity
        }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
