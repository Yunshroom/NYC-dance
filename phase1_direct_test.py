"""
Phase 1 direct endpoint test — try calling the discovered endpoints
without a browser, using plain HTTP.
"""

import json
import time
import urllib.request
import urllib.error
from pathlib import Path

OUT = Path(__file__).parent / "phase1_output"
OUT.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://brickhousedance.com/",
}

def fetch(url, extra_headers=None, label=""):
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", errors="replace")
            print(f"  [OK {r.status}] {label or url[:80]}")
            print(f"         size={len(body)} content-type={r.headers.get('Content-Type','?')}")
            return r.status, body, dict(r.headers)
    except urllib.error.HTTPError as e:
        print(f"  [HTTP {e.code}] {label or url[:80]}")
        return e.code, "", {}
    except Exception as ex:
        print(f"  [ERR] {label or url[:80]} — {ex}")
        return 0, "", {}


# ─── BRICKHOUSE ────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("BRICKHOUSE — Mindbody widget endpoints")
print("="*60)

# Main schedule JSON — seen during capture
bh_schedule_url = (
    "https://widgets.mindbodyonline.com/widgets/schedules/5f43835d68c.json"
    "?mobile=false&version=1&utm_params="
)
status, body, resp_headers = fetch(bh_schedule_url, label="BH schedule JSON")
if status == 200 and body:
    (OUT / "brickhouse_schedule_raw.json").write_text(body)
    # Try to parse as JSON (it may be JSONP wrapped)
    try:
        data = json.loads(body)
        print(f"         ✓ Valid JSON, top-level keys: {list(data.keys())[:6]}")
        (OUT / "brickhouse_schedule.json").write_text(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        if body.strip().startswith("jQuery") or body.strip().startswith("callback"):
            print("         → JSONP (not plain JSON, needs callback stripping)")
        else:
            print(f"         → Not JSON. First 200 chars: {body[:200]}")

# load_markup (JSONP) — also seen
bh_markup_url = (
    "https://widgets.mindbodyonline.com/widgets/schedules/43835/load_markup"
    "?callback=mycallback&mobile=false"
)
status2, body2, _ = fetch(bh_markup_url, label="BH load_markup (JSONP)")
if status2 == 200 and body2:
    (OUT / "brickhouse_load_markup_raw.txt").write_text(body2)
    print(f"         First 300 chars: {body2[:300]}")

# store_deploy_url
bh_store_url = (
    "https://widgets.mindbodyonline.com/widgets/widget/5f43835d68c/store_deploy_url.json"
    "?callback=mycallback"
)
status3, body3, _ = fetch(bh_store_url, label="BH store_deploy_url")
if status3 == 200 and body3:
    (OUT / "brickhouse_store_deploy.txt").write_text(body3)
    print(f"         First 200 chars: {body3[:200]}")


# ─── MODEGA ────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("MODEGA — Arketa/SutraPro API endpoints")
print("="*60)

modega_headers = {
    "Referer": "https://sutrapro.com/",
    "Origin": "https://sutrapro.com",
}

# Current week's start_time — use epoch of current Monday-ish
# The captured timestamps appear to be weekly; use one we know worked
# from the capture: 1782792000 (a recent week)
import datetime
now = datetime.datetime.utcnow()
# Round down to nearest week (Sunday midnight UTC)
epoch_base = int(datetime.datetime(2025, 1, 5, 0, 0, 0).timestamp())  # a known Sunday
weeks_since = (int(now.timestamp()) - epoch_base) // (7 * 86400)
this_week_ts = epoch_base + weeks_since * 7 * 86400
print(f"  Using start_time={this_week_ts} ({datetime.datetime.utcfromtimestamp(this_week_ts).isoformat()})")

modega_url = (
    f"https://sutrapro.com/api/widget/data"
    f"?widgetName=modega&type=classes&start_time={this_week_ts}"
)
status4, body4, resp4 = fetch(
    modega_url,
    extra_headers=modega_headers,
    label=f"Modega classes (start_time={this_week_ts})"
)
if status4 == 200 and body4:
    (OUT / "modega_schedule_raw.json").write_text(body4)
    try:
        data4 = json.loads(body4)
        print(f"         ✓ Valid JSON")
        if isinstance(data4, list):
            print(f"         → Array of {len(data4)} items")
            if data4:
                print(f"         → Sample item keys: {list(data4[0].keys())[:8]}")
        elif isinstance(data4, dict):
            print(f"         → Dict keys: {list(data4.keys())[:8]}")
        (OUT / "modega_schedule.json").write_text(json.dumps(data4, indent=2))
    except json.JSONDecodeError:
        print(f"         → Not JSON. First 300: {body4[:300]}")

# Also try next week
next_week_ts = this_week_ts + 7 * 86400
modega_url2 = (
    f"https://sutrapro.com/api/widget/data"
    f"?widgetName=modega&type=classes&start_time={next_week_ts}"
)
status5, body5, _ = fetch(
    modega_url2,
    extra_headers=modega_headers,
    label=f"Modega classes next week (start_time={next_week_ts})"
)
if status5 == 200 and body5:
    (OUT / "modega_schedule_next_week_raw.json").write_text(body5)
    try:
        data5 = json.loads(body5)
        if isinstance(data5, list):
            print(f"         → {len(data5)} classes next week")
    except Exception:
        pass

# Also try the captured known-good timestamp from the run
known_ts = 1782792000
modega_url3 = (
    f"https://sutrapro.com/api/widget/data"
    f"?widgetName=modega&type=classes&start_time={known_ts}"
)
status6, body6, _ = fetch(
    modega_url3,
    extra_headers=modega_headers,
    label=f"Modega classes known-ts={known_ts}"
)

print("\nDone — check phase1_output/ for raw responses.")
