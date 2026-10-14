# Build portable Windows app (default: one file). Always without UPX.
# One file:  powershell -File scripts/build_windows.ps1
# Folder:    powershell -File scripts/build_windows.ps1 -Onedir

param(
    [switch]$Onedir
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if ($env:PYTHON) {
    $Python = $env:PYTHON
} else {
    $VenvWorks = $false
    if (Test-Path $VenvPython) {
        $ErrorActionPreference = "Continue"
        & $VenvPython -c "import sys" 2>$null
        $VenvWorks = $LASTEXITCODE -eq 0
        $ErrorActionPreference = "Stop"
    }
    if (-not $VenvWorks) {
        $SystemPython = (Get-Command python).Source
        Write-Host "Creating build environment using $SystemPython..."
        & $SystemPython -m venv --clear (Join-Path $Root ".venv")
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    $Python = $VenvPython
}

$PreviousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -c "from importlib.metadata import version; import PyInstaller, PySide6, pymupdf, rapidocr, onnxruntime; assert version('rapidocr') == '3.9.2'"
$DependencyCheckExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorPreference
if ($DependencyCheckExit -ne 0) {
    Write-Host "Installing build dependencies..."
    & $Python -m pip install --no-cache-dir -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -c "from importlib.metadata import version; assert version('rapidocr') == '3.9.2'"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $Python scripts/download_ocr_models.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Name = "Listorez2047"
$Entry = "src/listorez2047/__main__.py"
$Icon = "assets/icons/it.ico"

$Args = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", $Name,
    "--paths", "src",
    "--add-data", "src/listorez2047/locales;listorez2047/locales",
    "--add-data", "src/listorez2047/appearance;listorez2047/appearance",
    "--add-data", "help;help",
    "--add-data", "assets/icons;assets/icons",
    "--add-data", "assets/models;assets/models",
    "--collect-all", "rapidocr",
    "--exclude-module", "surya",
    "--exclude-module", "transformers",
    "--exclude-module", "torch",
    "--exclude-module", "torchvision",
    "--noupx"
)

if (-not $Onedir) {
    $Args += "--onefile"
}

if (Test-Path $Icon) {
    $Args += @("--icon", $Icon)
}

$Args += $Entry

Write-Host "PyInstaller $($Args -join ' ')"
& $Python -m PyInstaller @Args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Onedir) {
    Write-Host "Built portable folder: $Root\dist\$Name\"
} else {
    Write-Host "Built portable file: $Root\dist\$Name.exe"
}
