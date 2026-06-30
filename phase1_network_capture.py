"""
Phase 1: Capture network requests from JS-rendered booking widgets.
Identifies XHR/fetch calls that return class schedule data.
"""

import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

STUDIOS = {
    "brickhouse": {
        "url": "https://brickhousedance.com/open-classes/",
        "wait_selector": None,
        "wait_ms": 8000,
    },
    "modega": {
        "url": "https://sutrapro.com/modega",
        "wait_selector": None,
        "wait_ms": 8000,
    },
}

SCHEDULE_KEYWORDS = [
    "class", "schedule", "event", "session", "booking",
    "appointment", "occurrence", "slot", "course",
]

def looks_like_schedule(url: str, body: str) -> bool:
    url_lower = url.lower()
    if not any(kw in url_lower for kw in SCHEDULE_KEYWORDS):
        # Also check body for schedule-like content
        if len(body) < 100:
            return False
        body_lower = body.lower()
        hits = sum(1 for kw in SCHEDULE_KEYWORDS if kw in body_lower)
        if hits < 2:
            return False
    return True

def capture_requests(name: str, config: dict, out_dir: Path):
    print(f"\n{'='*60}")
    print(f"Capturing: {name} — {config['url']}")
    print(f"{'='*60}")

    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        def on_response(response):
            url = response.url
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type and "javascript" not in content_type:
                # still capture anything that might be schedule data
                pass
            if url.startswith("data:") or url.startswith("blob:"):
                return
            # Skip static assets
            skip_exts = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
                         ".woff", ".woff2", ".ttf", ".css", ".ico")
            if any(url.lower().endswith(e) for e in skip_exts):
                return
            try:
                body = response.body()
                text = body.decode("utf-8", errors="replace")
            except Exception:
                text = ""

            entry = {
                "url": url,
                "status": response.status,
                "content_type": content_type,
                "size": len(text),
                "request_headers": dict(response.request.headers),
                "response_headers": dict(response.headers),
                "body_snippet": text[:2000],
                "full_body": text,
            }
            captured.append(entry)

            flag = " *** SCHEDULE CANDIDATE ***" if looks_like_schedule(url, text) else ""
            print(f"  [{response.status}] {url[:100]}{flag}")

        page.on("response", on_response)

        try:
            page.goto(config["url"], timeout=30000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  Navigation error: {e}")

        # Wait for JS widgets to load
        page.wait_for_timeout(config["wait_ms"])

        # Try networkidle too
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Grab final rendered HTML
        html = page.content()
        (out_dir / f"{name}_rendered.html").write_text(html)

        browser.close()

    # Save all captured requests
    (out_dir / f"{name}_all_requests.json").write_text(
        json.dumps(captured, indent=2, default=str)
    )

    # Filter schedule candidates
    candidates = [
        r for r in captured
        if looks_like_schedule(r["url"], r["full_body"])
        or "json" in r["content_type"].lower()
    ]
    (out_dir / f"{name}_candidates.json").write_text(
        json.dumps(candidates, indent=2, default=str)
    )

    print(f"\n  Total requests captured: {len(captured)}")
    print(f"  Schedule candidates: {len(candidates)}")
    for c in candidates:
        print(f"    -> {c['url'][:120]}")

    return captured, candidates


def main():
    out_dir = Path(__file__).parent / "phase1_output"
    out_dir.mkdir(exist_ok=True)

    results = {}
    for name, config in STUDIOS.items():
        all_req, candidates = capture_requests(name, config, out_dir)
        results[name] = {"total": len(all_req), "candidates": len(candidates)}

    print("\n\nSummary:")
    for name, r in results.items():
        print(f"  {name}: {r['total']} total requests, {r['candidates']} candidates")
    print(f"\nOutputs saved to: {out_dir}")


if __name__ == "__main__":
    main()
