# Remove build/test junk. Does not delete source, .venv, or user config.
# Usage (from repo root):  powershell -File scripts/clean.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Cleaning $Root"

$Dirs = @(
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".tox",
    ".nox",
    "logs"
)
foreach ($d in $Dirs) {
    $p = Join-Path $Root $d
    if (Test-Path $p) {
        Remove-Item -Recurse -Force $p
        Write-Host "removed $d"
    }
}

Get-ChildItem -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

Get-ChildItem -Recurse -Force -File -Include *.pyc,*.pyo,*.pyd,.coverage -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\\\.venv\\|\\venv\\" } |
    Remove-Item -Force -ErrorAction SilentlyContinue

Get-ChildItem -Force -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

Get-ChildItem -Force -File -Filter "*.spec" -ErrorAction SilentlyContinue |
    Remove-Item -Force

Write-Host "Clean done."
