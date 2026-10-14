# Listorez2047
[English](README.md) · [Русский](README.ru.md)

> One practical job at work. Built, as usual, so the same kind of paperwork can be done again. Finished.

**Listorez2047** / **Листорез2047** started from a single applied task: a stack of uniform documents had to be taken apart. It was not left as a one-off script. The same tool covers any batch of similar documents that should become separate, clearly named files.

What it does:

- splits a multi-page PDF into **one file per page**
- names each file from a template
- uses OCR only to form the filename, not to retell the document
- lets you review pages in the window, or run the same job from the command line

The project is a finished offline tool.

**GitHub About:** A finished offline tool for uniform documents: split a PDF into one file per page and name each file from a template.

[Русский README](README.ru.md) · [ТЗ](TZ_RU.md) · [Task list](AGENT_TASKLIST_EN.md)

**Author:** vibic777 (`vibic@yandex.ru`)

**Download / Скачать:** [GitHub Releases](https://github.com/vibic777/Listorez2047/releases/latest) — Windows `Listorez2047.exe`

Windows build from source: `dist/Listorez2047.exe`  
Linux build: `dist/Listorez2047`

---

## Antivirus / VirusTotal (false positives)

Some antivirus engines on [VirusTotal](https://www.virustotal.com/) may flag the portable Windows build. That is a **false positive** on the packaging, not malware in the app or in RapidOCR/Qt.

**Why it happens**

- The release is a **PyInstaller `--onefile`** exe: at start it unpacks Python, DLLs, and OCR models into a temp folder (`%TEMP%\_MEI…`) and runs from there. Real droppers do the same, so heuristics often label it `Dropper.Agent` / generic “malware”.
- The exe is **not code-signed**. Unsigned self-extracting PE files are scored more aggressively.
- Builds are packed **without UPX** (`--noupx`) to avoid an extra false-positive trigger.

**What VirusTotal typically shows** (same packaging; a few engines out of ~60+)

| Engine (examples) | Label | Meaning |
|---|---|---|
| Zillya | `Dropper.Agent.Win32…` | Heuristic: self-extracting / packed agent |
| Generic / ML engines | `W32.Malware.…` / “Suspicious” | Structure/hash heuristics, not a known Trojan family |
| (zip builds) SentinelOne Static ML | `Suspicious Archive` | PE inside a zip archive |

Most engines stay **Undetected**. Source code and `python -m listorez2047` are not treated the same way — the hit is the single-file launcher.

**How to verify a release**

1. Prefer downloads from [GitHub Releases](https://github.com/vibic777/Listorez2047/releases/latest) only.
2. Check the SHA-256 published in the release notes against your file.
3. Open the hash on VirusTotal, e.g. `https://www.virustotal.com/gui/file/<SHA256>`.
4. If your AV quarantines the file, add an exception for this known app, or run from source.

A future **code-signing certificate** would reduce SmartScreen/AV noise; it is optional and not required for the program to work.

---

## What it does

OCR (RapidOCR / PP-OCRv5, CPU only) is used **only to fill the filename**. The original page is copied into a one-page PDF. Scans are images; digital PDFs already have a text layer.

- Draw fields on the page, or load a form profile (`.pdfocr.json`).
- Build names with `{1}`, `{2}` and counters such as `{235:+1}` / `{505:+1#}`.
- Work page by page, or run **Auto** on the whole file.
- Empty or ambiguous fields pause for review instead of saving silently.
- A bad formula or OCR pattern shows a warning; the app stays open.

Evaluate expression belongs in the **default value**, not the OCR pattern. Remember last value copies the last **applied** value (Apply or Save), not a raw OCR hit.

**Auto** recognizes pages in a background thread. The preview stays usable: zoom, pan, and Save view.

## Command-line help

The program is a desktop application. Run it with no options to open the window. The command line supports standard help and version output without starting Qt:

```text
Listorez2047.exe --help
Listorez2047.exe -h
Listorez2047.exe --version
python -m listorez2047 --help
```

There are no command-line PDF input/output arguments; choose files and folders in the interface.

## Features

- Digital PDF and scans
- Preview: zoom, fit, pan; field frames stick to the page
- Filename template `{1}`, `{2}` and counters `{505:+1}` / `{1:+1#}` (`+ - * %`), always-editable name
- Per-page flow and **Auto**
- Form profiles (`.pdfocr.json`)
- UI Russian / English, four skins and four icons
- Listorez document-splitting icon for the default skin and Windows executable
- Log file with DEBUG / INFO / WARNING / ERROR / CRITICAL (including unhandled Qt failures)
- Portable Windows `.exe` and Linux binary — no Python on the target machine

Hardware target: about **4 GB RAM**, **2–4 CPU cores**. Pages are processed sequentially and OCR uses CPU only. OCR rasterization is limited to the field crop and configured maximum side. Preview rendering remains separate from OCR rendering.

## Requirements (from source)

- Python 3.11 or 3.12, 64-bit
- Windows 10/11 or Linux x64
- See [requirements.txt](requirements.txt). PySide6 is pinned to 6.9.3. Surya, PyTorch, and CUDA are not included.
- `python -m pytest` for the test suite (install pytest separately if it is not available).

## Run from source

```bash
python -m pip install -r requirements.txt
python scripts/download_ocr_models.py
set PYTHONPATH=src
python -m listorez2047
```

The model download is only needed for running from source. The packaged app includes all PP-OCRv5 models; no network access is used during recognition.

On Linux / macOS: `export PYTHONPATH=src` and `python3 -m listorez2047`.

Logging is **off by default**. When enabled, choose TRACE / DEBUG / INFO / WARNING / ERROR / CRITICAL. Default path from source: `%APPDATA%\Listorez2047\Listorez2047.log` (or `~/.config/Listorez2047` on Linux).  
Packaged app: `Listorez2047.log` next to `Listorez2047.exe` / `Listorez2047`.

Output folder may be absolute or relative (checkbox); it is stored in the form profile. Missing folders are offered for creation.

Local settings: `%APPDATA%\Listorez2047\config.json`. If `config.json` sits next to the exe, that copy wins (portable mode). Older `%APPDATA%\PDFOCRsplitter` and `%APPDATA%\Listorez` are read once if the new folder is still empty.

## Build

```powershell
powershell -File scripts/build_windows.ps1
```

The build scripts download and SHA-256 verify the bundled PP-OCRv5 model files from the official RapidOCR model repository.

Output: `dist/Listorez2047.exe`. Faster-start folder: `powershell -File scripts/build_windows.ps1 -Onedir`.

Linux:

```bash
bash scripts/build_linux.sh
```

Output: `dist/Listorez2047`. Folder variant: `bash scripts/build_linux.sh --onedir`.

Clean (does not delete source, `.venv`, or user config):

```powershell
powershell -File scripts/clean.ps1
```

## Patterns

- `DD.M.DDDD` — full date with a numeric or written month → `01.06.2026`
- `DD.M` — day and month without year: `“27” March 2026` → `27.03` (quotes and year are skipped)
- `@{№}D{1,4}` — a context anchor for a number; `№`/`No` is matched but omitted from the value
- `D{1,4}` / `C+` — variable length without padding
- `DD.DD.DDDD` — numeric date with zero padding

In-app help: **F1**. Cheat sheet: **F2**.

## Reliability notes

- Output pages are first written to a temporary file in the destination folder and then moved into place without replacing an existing file.
- Profiles are written atomically and their field geometry is validated when loaded.
- If Auto cannot recognize a page, it records the error and continues without saving that page. Pages with empty or ambiguous values pause for review.
- OCR uses RapidOCR 3.9.2 with PP-OCRv5 ONNX models on CPU. The Windows build script downloads the five required models from the official RapidOCR ModelScope repository and verifies their SHA-256 checksums; the packaged application uses bundled models and works offline.
- Auto-deskew corrects small skew angles in the OCR crop. CPU threads, recognition languages, detector size, and recognition batch settings are applied to the ONNX engine. Only one language model is held at a time; selected languages run sequentially.

## Tests

```bash
set PYTHONPATH=src
python -m pytest
```

## License

License to be chosen; source and Windows releases are published at [github.com/vibic777/Listorez2047](https://github.com/vibic777/Listorez2047).

