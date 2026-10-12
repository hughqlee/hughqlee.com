#!/usr/bin/env python3
"""Render the home page's share images (og:image, twitter:image) from the home page itself.

  images/og-cover-ko.jpg   from index.html (Korean), for the Korean home, projects, knowledge, and
                           books pages
  images/og-cover.jpg      from en/index.html (English), for the English pages

Each is a 1200 x 630 picture of the home page's terminal window in the dark theme. The page is drawn
as it is, with CARD_CSS below laid over it so that it fits the card: the name, role, and experience
rows and the prompt's past commands are left out, and the site map (ls ~) moves beside the banner.
Run it after the home page changes, from the repository root (folders starting with "_" are not
published by GitHub Pages):
    python3 _scripts/build_og.py
It needs Google Chrome (run headless; set CHROME to use another Chrome or Chromium binary) and macOS's
sips, which scales the 2x render down to 1200 x 630 and writes the JPEG.
"""
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CARDS = {"index.html": "images/og-cover-ko.jpg", "en/index.html": "images/og-cover.jpg"}
WIDTH, HEIGHT, SCALE = 1200, 630, 2

CARD_CSS = """
html, body { width: 1200px; height: 630px; overflow: hidden; }
body { display: flex; align-items: center; justify-content: center; min-height: 0; }
.page { width: 1104px; margin: 0; padding: 0; }
.cursor { animation: none; }
.terminal-body {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    grid-template-rows: auto auto auto auto;
    column-gap: 48px;
    padding: 30px 36px 34px;
}
.terminal-body > .prompt-line:first-child { grid-column: 1; grid-row: 1; }
.banner { grid-column: 1; grid-row: 2; margin: 16px 0 0 !important; }
.ascii { font-size: 25px; }
.caption { grid-column: 1; grid-row: 3; margin: 14px 0 0 !important; font-size: 15px; }
.bio { grid-column: 1; grid-row: 4; margin: 34px 0 0 !important; gap: 12px; }
.statement { font-size: 38px; }
.intro { font-size: 18px; }
.kv-list { display: none; }
.kv-list + .prompt-line { grid-column: 2; grid-row: 1; margin: 0 !important; }
.routes-nav { grid-column: 2; grid-row: 2 / span 2; align-self: start; margin: 16px 0 0 !important; }
.route { grid-template-columns: minmax(0, 1fr) auto; padding: 16px 18px; }
.route-name { font-size: 18px; }
.route-desc { display: none; }
.shell-session { grid-column: 2; grid-row: 4; align-self: end; margin: 0 !important; }
.shell-log { display: none; }
"""


def screenshot(url, png, profile, timeout=60):
    """Headless Chrome's --screenshot. Chrome can stay running after it writes the file, so wait for a
    complete PNG and then stop it (with its helper processes)."""
    chrome = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
         "--use-mock-keychain", "--password-store=basic", f"--user-data-dir={profile}",
         f"--window-size={WIDTH},{HEIGHT}", f"--force-device-scale-factor={SCALE}", f"--screenshot={png}", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        deadline = time.monotonic() + timeout
        while not (png.exists() and png.read_bytes().endswith(b"IEND\xaeB`\x82")):
            if time.monotonic() > deadline:
                sys.exit(f"Chrome wrote no screenshot of {url} in {timeout} s")
            if chrome.poll() is not None and not png.exists():
                sys.exit(f"Chrome exited ({chrome.returncode}) without a screenshot of {url}")
            time.sleep(0.2)
    finally:
        if chrome.poll() is None:
            os.killpg(chrome.pid, signal.SIGTERM)
            try:
                chrome.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(chrome.pid, signal.SIGKILL)


def render(page, out):
    doc = (ROOT / page).read_text(encoding="utf-8")
    # The dark theme whatever the renderer prefers, and the card stylesheet after the page's own.
    extra = f'<script>document.documentElement.dataset.theme = "dark";</script>\n<style>{CARD_CSS}</style>\n</head>'
    if doc.count("</head>") != 1:
        sys.exit(f"{page}: expected one </head>")
    doc = doc.replace("</head>", extra)
    with tempfile.TemporaryDirectory() as tmp:
        html, png = Path(tmp) / "card.html", Path(tmp) / "card.png"
        html.write_text(doc, encoding="utf-8")
        screenshot(html.as_uri(), png, Path(tmp) / "profile")
        subprocess.run(["sips", "-z", str(HEIGHT), str(WIDTH), "-s", "format", "jpeg", "-s", "formatOptions", "90",
                        str(png), "--out", str(ROOT / out)], check=True, capture_output=True)
    print(f"wrote {out} from {page}")


def main():
    if not Path(CHROME).exists():
        sys.exit(f"Chrome not found at {CHROME}: set CHROME to a Chrome or Chromium binary")
    for page, out in CARDS.items():
        render(page, out)


if __name__ == "__main__":
    main()
