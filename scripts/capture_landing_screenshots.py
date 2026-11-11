#!/usr/bin/env python
"""Refresh the landing-page screenshots from a running copy of the app.

The screenshots show example data and a month name ("November 2026"), so they age.
Run this whenever the interface changes, or every few months, then commit the images.

    python manage.py runserver 8000           # in one terminal
    python scripts/capture_landing_screenshots.py   # in another

It clicks "Try the demo" (a fresh demo account is created and deleted, so no real data is
touched), hides the demo banner, the demo guide and the floating buttons (so the images show what a normal account sees), and writes four JPEGs to
static/img/shots/: hero (phone), dashboard, budgets, goals.

Needs (dev only, not in requirements.txt):  pip install playwright pillow  &&  playwright install chromium
Optional: BASE_URL (default http://localhost:8000), CHROMIUM_PATH (use an existing Chromium).
"""
import io
import os
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "shots"
HIDE = ".demo-banner,.demo-tour,.fab-group{display:none!important}"


def start_demo(page):
    page.goto(BASE_URL + "/")
    page.click('.hero__cta button:has-text("Try the demo")')
    page.wait_for_url("**/app/**", timeout=15000)
    page.wait_for_timeout(1500)


def tidy(page, extra=""):
    page.evaluate(
        """css => {
            document.querySelectorAll('.toast').forEach(t => t.remove());
            const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
            window.scrollTo(0, 0);
        }""",
        HIDE + extra,
    )
    page.wait_for_timeout(300)


def save(png_bytes, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img.save(OUT / f"{name}.jpg", quality=82, optimize=True, progressive=True)
    print(f"  {name}.jpg  {img.size[0]}x{img.size[1]}")


def main():
    launch_args = {}
    if os.environ.get("CHROMIUM_PATH"):
        launch_args["executable_path"] = os.environ["CHROMIUM_PATH"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_args)
        print("Phone view (hero)")
        ctx = browser.new_context(viewport={"width": 390, "height": 800}, device_scale_factor=1.5, has_touch=True, is_mobile=True)
        page = ctx.new_page()
        start_demo(page)
        tidy(page, ".subnav{display:none!important}")  # no half-cut tabs in the phone frame
        save(page.screenshot(clip={"x": 0, "y": 0, "width": 390, "height": 800}), "hero")
        ctx.close()

        print("Desktop cards")
        ctx = browser.new_context(viewport={"width": 700, "height": 1500}, device_scale_factor=1.5)
        page = ctx.new_page()
        start_demo(page)
        # Narrow viewport = bigger text once the image is shrunk on the landing page.
        # max_h crops long pages so each screenshot stays about as tall as it is wide.
        for name, path, wait, max_h in (("dashboard", "/app/", 1700, 900), ("budgets", "/app/budgets/", 900, 760), ("goals", "/app/goals/", 1400, 760)):
            page.goto(BASE_URL + path)
            page.wait_for_timeout(wait)
            tidy(page)
            box = page.locator("main > section.glass-card").first.bounding_box()
            box["height"] = min(box["height"], max_h)
            save(page.screenshot(clip=box), name)
        ctx.close()
        browser.close()
    print("Done. Check the images, then commit static/img/shots/.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # keep the failure readable for a one-off dev script
        sys.exit(f"Could not capture screenshots: {exc}\nIs the app running at {BASE_URL}?")
