#!/usr/bin/env python3
"""
Modega / Mover's Bodega — class schedule scraper.

Data source: Arketa/SutraPro public widget API (plain HTTP, no browser required).
  https://sutrapro.com/api/widget/data?widgetName=modega&type=classes&start_time=<unix_ts>

The API is paginated by week: pass a Unix timestamp for the start of any week
to get that week's classes. We fetch several weeks forward.

No auth, no CORS restriction, no bot protection observed. Plain GET works.
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ── Config ─────────────────────────────────────────────────────────────────────

WIDGET_NAME = "modega"
BASE_URL = "https://sutrapro.com/api/widget/data"
WEEKS_TO_FETCH = 4  # how many weeks of schedule to retrieve (starting from this week)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://sutrapro.com/",
    "Origin": "https://sutrapro.com",
}

OUTPUT_FILE = Path(__file__).parent / "modega_schedule.json"


# ── Helpers ────────────────────────────────────────────────────────────────────

def week_start_timestamps(num_weeks: int) -> list[int]:
    """Return Unix timestamps for the start of each of the next N weeks.

    The SutraPro API appears to use Sunday 00:00 UTC as the week boundary
    based on observed captured timestamps (all divisible by 604800 offset
    from a known Sunday epoch).
    """
    now = datetime.now(timezone.utc)
    # Roll back to the most recent Sunday midnight UTC
    days_since_sunday = now.weekday() + 1  # weekday(): Mon=0..Sun=6; +1 makes Sun=7->0
    if days_since_sunday == 7:
        days_since_sunday = 0
    this_sunday = now - timedelta(
        days=days_since_sunday,
        hours=now.hour,
        minutes=now.minute,
        seconds=now.second,
        microseconds=now.microsecond,
    )
    return [int((this_sunday + timedelta(weeks=i)).timestamp()) for i in range(num_weeks)]


def fetch_week(start_ts: int) -> list[dict]:
    url = f"{BASE_URL}?widgetName={WIDGET_NAME}&type=classes&start_time={start_ts}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for start_time={start_ts}", file=sys.stderr)
        return []
    return data.get("data", {}).get("classes", [])


# ── Normalise ──────────────────────────────────────────────────────────────────

_STUDIO_NAMES = {"Modega", "Mover's Bodega, LLC", "Mover's Bodega", "Mover's Bodega LLC"}

def _resolve_instructor(raw: dict) -> str:
    """
    Sutra returns instructor_name = studio org name when a guest teacher hosts.
    The real teacher lives in host_name / hostName / hostData[0].name.
    Priority: host_name (if not studio) > instructor_name (if not studio) > hostData name > ""
    """
    candidates = [
        raw.get("host_name") or raw.get("hostName"),
        raw.get("instructor_name"),
    ]
    # hostData array fallback
    host_data = raw.get("hostData") or []
    if host_data and isinstance(host_data, list):
        candidates.append(host_data[0].get("name"))

    for name in candidates:
        if name and name.strip() and name.strip() not in _STUDIO_NAMES:
            return name.strip()
    return ""   # will be mapped to "Modega Staff" in build_site.py

def normalise(raw: dict) -> dict:
    """Flatten the Arketa class object to the fields we care about."""
    start_ts = raw.get("start_time")
    end_ts = raw.get("end_time")

    def ts_to_iso(ts):
        if not ts:
            return ""
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return str(ts)

    start_iso = ts_to_iso(start_ts)
    end_iso = ts_to_iso(end_ts)

    duration_minutes = None
    if start_ts and end_ts:
        duration_minutes = int((end_ts - start_ts) / 60)

    # Booking URL: SutraPro widget links use the class id
    class_id = raw.get("id", "")
    booking_url = f"https://sutrapro.com/modega/checkout/{class_id}" if class_id else ""

    return {
        "class_id": class_id,
        "class_name": raw.get("class_name") or raw.get("name", ""),
        "date": start_iso[:10] if start_iso else "",
        "start_time": start_iso,
        "end_time": end_iso,
        "duration_minutes": duration_minutes,
        "instructor": _resolve_instructor(raw),
        "location": (raw.get("location") or {}).get("name") or raw.get("location_name", ""),
        "location_address": (raw.get("location") or {}).get("address", ""),
        "location_type": raw.get("location_type", ""),
        "description": raw.get("class_about") or raw.get("description", ""),
        "max_capacity": raw.get("max_capacity"),
        "total_booked": raw.get("total_booked"),
        "waitlist_length": raw.get("waitlistLength", 0),
        "is_bookable": raw.get("isBookable", False),
        "is_canceled": raw.get("canceled", False),
        "price": raw.get("price"),
        "minimum_price": raw.get("minimum_price"),
        "booking_url": booking_url,
        "source_url": "https://sutrapro.com/modega",
        "studio": "Modega / Mover's Bodega",
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"Fetching Modega schedule ({WEEKS_TO_FETCH} weeks)...")
    timestamps = week_start_timestamps(WEEKS_TO_FETCH)

    seen_ids: set[str] = set()
    all_classes: list[dict] = []

    for ts in timestamps:
        week_label = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        raw_classes = fetch_week(ts)
        new = 0
        for raw in raw_classes:
            cid = raw.get("id", "")
            if cid and cid in seen_ids:
                continue  # deduplicate (weeks can overlap slightly)
            if cid:
                seen_ids.add(cid)
            norm = normalise(raw)
            if not norm["is_canceled"]:
                all_classes.append(norm)
                new += 1
        print(f"  Week {week_label}: {len(raw_classes)} raw → {new} new non-canceled classes")

    # Sort by start_time
    all_classes.sort(key=lambda c: c["start_time"])

    output = {
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "studio": "Modega / Mover's Bodega",
        "source_url": "https://sutrapro.com/modega",
        "endpoint_pattern": f"{BASE_URL}?widgetName={WIDGET_NAME}&type=classes&start_time=<unix_ts>",
        "weeks_fetched": WEEKS_TO_FETCH,
        "class_count": len(all_classes),
        "classes": all_classes,
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Saved {len(all_classes)} classes to {OUTPUT_FILE}")

    if all_classes:
        print("\nSample class:")
        print(json.dumps(all_classes[0], indent=2))


if __name__ == "__main__":
    main()
