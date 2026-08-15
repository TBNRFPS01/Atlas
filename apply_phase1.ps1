$ErrorActionPreference = 'Stop'
$ui = Join-Path $PSScriptRoot 'ATLAS_UI.html'
if (!(Test-Path $ui)) { throw 'ATLAS_UI.html not found.' }

$html = Get-Content $ui -Raw

$headAdditions = @'
<link rel="stylesheet" href="atlas_phase1.css">
<link rel="stylesheet" href="atlas_customizer.css">
<script src="atlas_customizer.js" defer></script>
'@

# Add any missing Phase 1 Redux assets without duplicating existing links.
if ($html -notmatch 'atlas_phase1\.css') {
    $html = $html -replace '(</head>)', "$headAdditions`r`n`$1"
} else {
    if ($html -notmatch 'atlas_customizer\.css') {
        $html = $html -replace '(</head>)', "<link rel=`"stylesheet`" href=`"atlas_customizer.css`">`r`n`$1"
    }
    if ($html -notmatch 'atlas_customizer\.js') {
        $html = $html -replace '(</head>)', "<script src=`"atlas_customizer.js`" defer></script>`r`n`$1"
    }
}

Set-Content $ui $html -Encoding utf8
Write-Host 'ATLAS Phase 1 Redux assets are linked.' -ForegroundColor Cyan
Write-Host 'Default theme: Ivory Whisper. Theme picker enabled.' -ForegroundColor Green
Write-Host 'Done. Open ATLAS_UI.html to preview.' -ForegroundColor Green
