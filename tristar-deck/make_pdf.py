#!/usr/bin/env python3
"""Render triStar.html → TriStar-Deck-V2.pdf using Chrome headless."""

import subprocess, sys, tempfile, os, re
from pathlib import Path

DECK_DIR   = Path(__file__).parent
HTML_SRC   = DECK_DIR / "triStar.html"
PDF_OUT    = DECK_DIR / "TriStar-Deck-V2.pdf"
CHROME     = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PRINT_CSS = """
<style id="print-override">
@page {
  size: 1280px 720px;
  margin: 0;
}
@media print {
  html, body {
    width: 1280px !important;
    height: auto !important;
    overflow: visible !important;
    background: #1b1c2a;
  }
  .nav-hint { display: none !important; }
  .deck {
    position: static !important;
    width: 1280px !important;
    height: auto !important;
    background: #1b1c2a !important;
  }
  .slide {
    position: static !important;
    inset: auto !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    width: 1280px !important;
    height: 720px !important;
    page-break-after: always !important;
    break-after: page !important;
    overflow: hidden !important;
    display: grid !important;
    grid-template-columns: 40% 60% !important;
  }
  .slide-cover {
    display: flex !important;
    flex-direction: row !important;
    grid-template-columns: unset !important;
  }
  .slide:last-of-type {
    page-break-after: avoid !important;
    break-after: avoid !important;
  }
  .p-notes { display: none !important; }
  /* Ensure background colours are printed */
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
}
</style>
"""

def build_print_html(src: Path) -> str:
    html = src.read_text(encoding="utf-8")
    # Inject print CSS just before </head>
    html = html.replace("</head>", PRINT_CSS + "\n</head>", 1)
    return html


def main():
    print(f"Reading {HTML_SRC} ...")
    print_html = build_print_html(HTML_SRC)

    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False,
        dir=DECK_DIR, mode="w", encoding="utf-8"
    ) as tf:
        tf.write(print_html)
        tmp_path = Path(tf.name)

    print(f"Temp print file: {tmp_path}")
    print(f"Launching Chrome headless → {PDF_OUT} ...")

    cmd = [
        CHROME,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-extensions",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={PDF_OUT}",
        f"--window-size=1280,720",
        f"file://{tmp_path.resolve()}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print("STDERR:", result.stderr[:1000])
        sys.exit(1)

    if PDF_OUT.exists():
        size_kb = PDF_OUT.stat().st_size // 1024
        print(f"\n✅  TriStar-Deck-V2.pdf created ({size_kb} KB) → {PDF_OUT}")
    else:
        print("ERROR: PDF not created. Chrome output:")
        print(result.stdout[:500])
        print(result.stderr[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
