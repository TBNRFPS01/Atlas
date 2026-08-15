$ErrorActionPreference = 'Stop'
$ui = Join-Path $PSScriptRoot 'ATLAS_UI.html'
if (!(Test-Path $ui)) { throw 'ATLAS_UI.html not found.' }

$html = Get-Content $ui -Raw
$link = '<link rel="stylesheet" href="atlas_phase1.css">'

if ($html -notmatch 'atlas_phase1\.css') {
    $html = $html -replace '(</head>)', "$link`r`n`$1"
    Set-Content $ui $html -Encoding utf8
    Write-Host 'Phase 1 styling linked to ATLAS_UI.html.' -ForegroundColor Cyan
} else {
    Write-Host 'Phase 1 styling is already linked.' -ForegroundColor Yellow
}

Write-Host 'Done. Open ATLAS_UI.html to preview Phase 1.' -ForegroundColor Green
