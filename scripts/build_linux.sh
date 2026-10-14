#!/usr/bin/env bash
# Build portable Linux app.
# Default (one file):  bash scripts/build_linux.sh
# Folder (faster start):  bash scripts/build_linux.sh --onedir
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
ONEDIR=0
if [[ "${1:-}" == "--onedir" ]]; then
  ONEDIR=1
fi

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "Installing build dependencies..."
  "$PYTHON" -m pip install -r requirements.txt
fi

"$PYTHON" -c "from importlib.metadata import version; import rapidocr, onnxruntime; assert version('rapidocr') == '3.9.2'"
"$PYTHON" scripts/download_ocr_models.py

NAME="Listorez2047"
ENTRY="src/listorez2047/__main__.py"
ICON="assets/icons/it.png"

ARGS=(
  --noconfirm
  --clean
  --windowed
  --name "$NAME"
  --paths src
  --add-data "src/listorez2047/locales:listorez2047/locales"
  --add-data "src/listorez2047/appearance:listorez2047/appearance"
  --add-data "help:help"
  --add-data "assets/icons:assets/icons"
  --add-data "assets/models:assets/models"
  --collect-all rapidocr
  --noupx
)

if [[ "$ONEDIR" -eq 0 ]]; then
  ARGS+=(--onefile)
fi

if [[ -f "$ICON" ]]; then
  ARGS+=(--icon "$ICON")
fi

ARGS+=("$ENTRY")

echo "PyInstaller ${ARGS[*]}"
"$PYTHON" -m PyInstaller "${ARGS[@]}"
if [[ "$ONEDIR" -eq 1 ]]; then
  echo "Built portable folder: $ROOT/dist/$NAME/"
else
  echo "Built portable file: $ROOT/dist/$NAME"
fi
