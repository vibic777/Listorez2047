"""Fetch pinned PP-OCRv5 ONNX assets; the shipped app never downloads models."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "models"
BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv5"
MODELS = {
    "det/ch_PP-OCRv5_det_mobile.onnx": "4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae",
    "cls/ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx": "54379ae5174d026780215fc748a7f31910dee36818e63d49e17dc598ecc82df7",
    "rec/eslav_PP-OCRv5_rec_mobile.onnx": "08705d6721849b1347d26187f15a5e362c431963a2a62bfff4feac578c489aab",
    "rec/latin_PP-OCRv5_rec_mobile.onnx": "b20bd37c168a570f583afbc8cd7925603890efbcdc000a59e22c269d160b5f5a",
    "rec/ch_PP-OCRv5_rec_mobile.onnx": "5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for relative_name, expected in MODELS.items():
        name = Path(relative_name).name
        target = DEST / name
        if target.exists() and sha256(target) == expected:
            print(f"Verified {name}")
            continue
        fd, temp_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".part", dir=DEST)
        temp = Path(temp_name)
        try:
            digest = hashlib.sha256()
            with os.fdopen(fd, "wb") as output, urlopen(f"{BASE}/{relative_name}", timeout=60) as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            actual = digest.hexdigest()
            if actual != expected:
                raise RuntimeError(f"SHA-256 mismatch for {name}: {actual}")
            os.replace(temp, target)
            print(f"Downloaded and verified {name}")
        finally:
            temp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
