#!/usr/bin/env python3
"""Render index.html → TriStar-Deck-V2.pdf using Playwright (Chromium)."""

import asyncio, re, sys
from pathlib import Path

DECK_DIR = Path(__file__).parent
HTML_SRC = DECK_DIR / "index.html"
PDF_OUT  = DECK_DIR / "TriStar-Deck-V2.pdf"

# 16:9 slide at 96 dpi  →  1280px × 720px  =  ~338mm × 190mm
PAGE_W_MM = 338
PAGE_H_MM = 190

PRINT_CSS = f"""
@page {{
  size: {PAGE_W_MM}mm {PAGE_H_MM}mm;
  margin: 0;
}}
html, body {{
  width: {PAGE_W_MM}mm !important;
  height: auto !important;
  overflow: visible !important;
  background: #1b1c2a;
}}
.nav-hint {{ display: none !important; }}
.deck {{
  position: static !important;
  width: {PAGE_W_MM}mm !important;
  height: auto !important;
  background: #1b1c2a !important;
}}
.slide {{
  position: static !important;
  inset: auto !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  width: {PAGE_W_MM}mm !important;
  height: {PAGE_H_MM}mm !important;
  overflow: hidden !important;
  page-break-after: always !important;
  break-after: page !important;
  display: grid !important;
  grid-template-columns: 40% 60% !important;
}}
.slide:last-of-type {{
  page-break-after: avoid !important;
  break-after: avoid !important;
}}
.p-notes {{ display: none !important; }}
* {{
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
}}
"""


def build_print_html(src: Path) -> str:
    html = src.read_text(encoding="utf-8")

    # Inline assets/style.css (relative path won't resolve in some contexts)
    css_path = DECK_DIR / "assets" / "style.css"
    if css_path.exists():
        html = html.replace(
            '<link rel="stylesheet" href="assets/style.css">',
            f"<style>{css_path.read_text(encoding='utf-8')}</style>", 1,
        )

    # Remove deck.js (hides inactive slides on DOMContentLoaded)
    html = re.sub(r'<script src="assets/deck\.js"></script>', "", html)

    # Force all slides visible before first paint
    html = html.replace(
        "<body>",
        "<body><style>" + PRINT_CSS + "</style>",
        1,
    )

    # Also unlock via JS for any lingering inline opacity
    html = html.replace(
        "</body>",
        "<script>document.querySelectorAll('.slide').forEach(function(s){"
        "s.style.cssText+='opacity:1!important;position:static!important;';});"
        "</script>\n</body>",
        1,
    )
    return html


async def main() -> None:
    from playwright.async_api import async_playwright

    print(f"Source  : {HTML_SRC}")
    print_html = build_print_html(HTML_SRC)

    tmp_path = DECK_DIR / "_print_tmp.html"
    tmp_path.write_text(print_html, encoding="utf-8")
    print(f"Temp    : {tmp_path}  ({len(print_html)//1024} KB)")

    PDF_OUT.unlink(missing_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        page    = await browser.new_page(
            viewport={"width": 1280, "height": 720}
        )

        print("Loading page ...")
        await page.goto(
            f"file://{tmp_path.resolve()}",
            wait_until="networkidle",
            timeout=30_000,
        )

        # Extra wait for animations / fonts
        await asyncio.sleep(2)

        print("Generating PDF ...")
        await page.pdf(
            path=str(PDF_OUT),
            width=f"{PAGE_W_MM}mm",
            height=f"{PAGE_H_MM}mm",
            print_background=True,
        )

        await browser.close()

    tmp_path.unlink(missing_ok=True)

    if PDF_OUT.exists() and PDF_OUT.stat().st_size > 50_000:
        size_kb = PDF_OUT.stat().st_size // 1024
        pages   = len(re.findall(rb"/Type\s*/Page[^s]", PDF_OUT.read_bytes()))
        print(f"\n✅  TriStar-Deck-V2.pdf  |  {pages} slides  |  {size_kb} KB")
        print(f"    {PDF_OUT}")
    else:
        sz = PDF_OUT.stat().st_size if PDF_OUT.exists() else 0
        print(f"\nERROR: PDF missing or too small ({sz} bytes)")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
