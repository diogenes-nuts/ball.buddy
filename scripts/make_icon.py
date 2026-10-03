"""Build-time: render assets/icon.ico (256x256 PNG-in-ICO) from the app mark.

Usage: .venv\\Scripts\\python scripts/make_icon.py  (offscreen, no display needed)
"""

import os
import struct
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must precede PySide6 import

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ball_buddy.ui.appicon import draw_app_icon  # noqa: E402


def make_ico(png_bytes: bytes, dest: Path) -> None:
    """Wrap PNG bytes in a minimal ICONDIR/ICONDIRENTRY container."""
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png_bytes), 22)
    dest.write_bytes(header + entry + png_bytes)


def main() -> None:
    QApplication([])
    image = draw_app_icon(256)
    with tempfile.TemporaryDirectory() as tmp:
        png_path = Path(tmp) / "icon.png"
        image.save(str(png_path), "PNG")
        png_bytes = png_path.read_bytes()
    dest = REPO_ROOT / "assets" / "icon.ico"
    dest.parent.mkdir(parents=True, exist_ok=True)
    make_ico(png_bytes, dest)
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
