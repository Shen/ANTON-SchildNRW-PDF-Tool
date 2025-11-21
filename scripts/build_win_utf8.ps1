param(
    [switch]$OneFile,
    [switch]$OneDir,
    [switch]$NoPause
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# UTF-8 Ein-/Ausgabe für korrekte Umlaute
[Console]::InputEncoding  = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding           = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONUTF8 = '1'

trap {
    Write-Host "Fehler beim Build:" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Druecken Sie Enter, um dieses Fenster zu schliessen" }
    exit 1
}

# Zum Repo-Root wechseln (Skript liegt unter ./scripts)
$ScriptDir = Split-Path -Parent $PSCommandPath
$Root = Split-Path -Parent $ScriptDir
Set-Location -Path $Root

# Python ermitteln (vollständiger Pfad)
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) { Write-Error "Python ist nicht installiert oder nicht im PATH." }
$Python = $PythonCmd.Source

# Pfade (alle relativ zum Repo-Root)
$StartPy = Join-Path $Root 'ANTON-Tool.py'
$ReqFile = Join-Path $Root 'requirements.txt'
# EXE direkt ins Hauptverzeichnis ablegen
$DistDir = $Root
$BuildDir = Join-Path $Root 'build'
$SpecDir = $Root

# Interaktive Auswahl, falls kein Modus übergeben wurde
$explicitChoice = $PSBoundParameters.ContainsKey('OneFile') -or $PSBoundParameters.ContainsKey('OneDir')
if (-not $explicitChoice) {
    Write-Host "Build-Variante waehlen:" -ForegroundColor Cyan
    Write-Host "  [J] Eine Datei (empfohlen)" -ForegroundColor Gray
    Write-Host "  [N] Ordner (schneller Build, groessere Ausgabe)" -ForegroundColor Gray
    $ans = Read-Host "Ein-Datei erstellen? (J/N) [J]"
    if ([string]::IsNullOrWhiteSpace($ans)) { $OneFileSelected = $true }
    elseif ($ans.Trim().ToLower() -in @('n','nein')) { $OneFileSelected = $false }
    else { $OneFileSelected = $true }
} else {
    if ($PSBoundParameters.ContainsKey('OneFile')) { $OneFileSelected = $true }
    elseif ($PSBoundParameters.ContainsKey('OneDir')) { $OneFileSelected = $false }
}

# Abhängigkeiten installieren (über python -m, damit Leerzeichen sicher sind)
& $Python -m pip install --upgrade pip pyinstaller
if (Test-Path -Path $ReqFile) { & $Python -m pip install -r $ReqFile }

# PyInstaller-Argumente als Array aufbauen
$pyiArgs = @(
    '--windowed',
    '--name', 'ANTON-Tool',
    '--distpath', $DistDir,
    '--workpath', $BuildDir,
    '--specpath', $SpecDir,
    '--noconfirm',
    '--clean',
    $StartPy
)
if ($OneFileSelected) { $pyiArgs += '--onefile' } else { $pyiArgs += '--onedir' }

& $Python -m PyInstaller @pyiArgs

Write-Host "Fertig. Artefakte unter: $DistDir" -ForegroundColor Green
if (-not $NoPause) { Read-Host "Druecken Sie Enter, um dieses Fenster zu schliessen" }
