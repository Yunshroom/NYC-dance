#!/usr/bin/env python3
"""
Broadway Dance Center — open class schedule scraper.

Data source: dance-schedule-unfold-studio.vercel.app/api/schedule
  (returns a pre-aggregated schedule; BDC events have studioId = "bdc")

Broadway Dance Center uses MindBody (site ID: 28329).
Studio site:  https://broadwaydancecenter.com/
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ── Config ─────────────────────────────────────────────────────────────────────

SOURCE_URL  = "https://dance-schedule-unfold-studio.vercel.app/api/schedule"
OUTPUT_FILE = Path(__file__).parent / "bdc_schedule.json"
BOOKING_URL = "https://clients.mindbodyonline.com/classic/ws?studioid=28329&stype=-103"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
}


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_schedule() -> dict:
    req = urllib.request.Request(SOURCE_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# ── Parse ──────────────────────────────────────────────────────────────────────

ET = timezone(timedelta(hours=-4))  # EDT (summer)

def parse_dt(iso: str):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(ET)
    except Exception:
        return None

def fmt_time(dt) -> str:
    if not dt:
        return ""
    return dt.strftime("%-I:%M %p")

def parse_bdc_classes(data: dict) -> list:
    events = data.get("events", [])
    bdc_events = [e for e in events if e.get("studioId") == "bdc"]

    out = []
    for e in bdc_events:
        start_dt = parse_dt(e.get("start", ""))
        end_dt   = parse_dt(e.get("end", ""))
        title    = e.get("title", "")

        date_key      = start_dt.strftime("%Y-%m-%d") if start_dt else ""
        start_display = fmt_time(start_dt)
        end_display   = fmt_time(end_dt)

        if start_dt and end_dt:
            duration_min = int((end_dt - start_dt).total_seconds() / 60)
        else:
            duration_min = e.get("durationMin")

        start_hour = (start_dt.hour + start_dt.minute / 60) if start_dt else -1

        out.append({
            "date":               date_key,
            "start_time":         start_dt.isoformat() if start_dt else "",
            "end_time":           end_dt.isoformat() if end_dt else "",
            "start_time_display": start_display,
            "end_time_display":   end_display,
            "duration_minutes":   duration_min,
            "start_hour":         start_hour,
            "class_name":         title,
            "instructor":         e.get("instructor", ""),
            "booking_url":        e.get("bookingUrl", BOOKING_URL),
            "is_canceled":        e.get("isCanceled", False),
            "is_full":            e.get("isFull", False),
            "spots_left":         e.get("spotsLeft"),
            "source_url":         "https://broadwaydancecenter.com/",
            "studio":             "Broadway Dance Center",
            "source_event_id":    e.get("id", ""),
        })

    return out


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Fetching Broadway Dance Center schedule…")
    try:
        data = fetch_schedule()
    except Exception as e:
        print(f"Fetch error: {e}", file=sys.stderr)
        sys.exit(1)

    generated_at = data.get("generatedAt", "")
    classes = parse_bdc_classes(data)

    canceled = sum(1 for c in classes if c.get("is_canceled"))
    full     = sum(1 for c in classes if c.get("is_full"))
    print(f"  {len(classes)} classes ({canceled} canceled, {full} full)")
    print(f"  Source data generated at: {generated_at}")

    output = {
        "scraped_at":          datetime.utcnow().isoformat() + "Z",
        "source_generated_at": generated_at,
        "studio":              "Broadway Dance Center",
        "source_url":          "https://broadwaydancecenter.com/",
        "data_source":         SOURCE_URL,
        "mindbody_site_id":    "28329",
        "class_count":         len(classes),
        "classes":             classes,
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Saved to {OUTPUT_FILE}")

    non_canceled = [c for c in classes if not c.get("is_canceled")]
    if non_canceled:
        print("\nSample class:")
        print(json.dumps(non_canceled[0], indent=2))


if __name__ == "__main__":
    main()
