"""Convert the SVG sheet to PDF / PNG with a headless Chromium browser (Edge or Chrome)."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CANDIDATES = [
    os.environ.get("SLD_BROWSER", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    *(shutil.which(n) or "" for n in ("msedge", "microsoft-edge", "google-chrome", "google-chrome-stable",
                                      "chrome", "chromium", "chromium-browser")),
]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: 420mm 297mm; margin: 0 }}
html, body {{ margin: 0; padding: 0; background: #fff }}
svg {{ display: block; width: 420mm; height: 297mm }}
</style></head><body>{svg}</body></html>"""


def find_browser():
    for c in CANDIDATES:
        if c and Path(c).exists():
            return c
    raise RuntimeError("No Edge/Chrome found. Set SLD_BROWSER to a Chromium browser executable.")


def _run(args):
    with tempfile.TemporaryDirectory() as profile:
        cmd = [find_browser(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               f"--user-data-dir={profile}", *args]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def write_html(svg, path):
    path.write_text(PAGE.format(svg=svg), encoding="utf-8")
    return path


def to_pdf(html_path, pdf_path):
    _run(["--no-pdf-header-footer", f"--print-to-pdf={Path(pdf_path).resolve()}",
          Path(html_path).resolve().as_uri()])
    return pdf_path


def to_png(html_path, png_path, scale=2):
    # 420 x 297 mm at 96 dpi = 1588 x 1123 CSS px
    _run([f"--screenshot={Path(png_path).resolve()}", "--window-size=1588,1123",
          f"--force-device-scale-factor={scale}", "--hide-scrollbars", Path(html_path).resolve().as_uri()])
    return png_path
