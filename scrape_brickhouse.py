#!/usr/bin/env python3
"""
Brickhouse NYC — open class schedule scraper.

Data source: Mindbody widget endpoint (plain HTTP, no browser required).
  https://widgets.mindbodyonline.com/widgets/schedules/43835/load_markup

The endpoint returns JSONP with HTML inside a `class_sessions` key.
We strip the JSONP wrapper, parse the HTML with BeautifulSoup, and
extract structured class objects.

If the widget HTML structure changes, the CSS selectors below are the
things most likely to break — search for "FRAGILE" comments.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, date
from pathlib import Path

from bs4 import BeautifulSoup


# ── Config ─────────────────────────────────────────────────────────────────────

WIDGET_ID = "43835"          # Mindbody studio widget ID; stable unless studio changes platform
WIDGET_TOKEN = "5f43835d68c" # appears in the healcode embed; change if widget is re-embedded

WEEKS_TO_FETCH = 4  # number of weeks to retrieve starting from today

def load_markup_url(start_date: str) -> str:
    """start_date: YYYY-MM-DD string (Monday of the desired week)."""
    import time
    ts = int(time.time() * 1000)
    return (
        f"https://widgets.mindbodyonline.com/widgets/schedules/{WIDGET_ID}/load_markup"
        f"?callback=_cb&options%5Bstart_date%5D={start_date}&_={ts}&mobile=false"
    )

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/javascript, application/javascript, */*; q=0.01",
    "Referer": "https://brickhousedance.com/",
}

OUTPUT_FILE = Path(__file__).parent / "brickhouse_schedule.json"


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_load_markup(start_date: str) -> dict:
    url = load_markup_url(start_date)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="replace")

    # Strip JSONP wrapper: _cb({...});
    json_str = re.sub(r"^[^(]+\(", "", raw).rstrip().rstrip(";").rstrip(")")
    return json.loads(json_str)


# ── Parse ──────────────────────────────────────────────────────────────────────

def parse_classes(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # FRAGILE: Mindbody widget wraps each day in .bw-widget__day, each class in .bw-session
    for day_div in soup.select(".bw-widget__day"):

        # FRAGILE: date is in a .bw-widget__date div with class like "date-2026-06-30"
        date_div = day_div.select_one(".bw-widget__date")
        date_str = ""
        if date_div:
            date_text = date_div.get_text(strip=True)  # e.g. "Tuesday, June 30"
            # Also try to extract from the CSS class for a stable parse
            date_class = next(
                (c for c in date_div.get("class", []) if c.startswith("date-")),
                None,
            )
            if date_class:
                date_str = date_class.replace("date-", "")  # "2026-06-30"
            else:
                # Fallback: parse text
                try:
                    dt = datetime.strptime(date_text, "%A, %B %d")
                    date_str = dt.strftime(f"{datetime.now().year}-%m-%d")
                except ValueError:
                    date_str = date_text

        for session in day_div.select(".bw-session"):  # FRAGILE: .bw-session
            cls: dict = {
                "date": date_str,
                "source_url": "https://brickhousedance.com/open-classes/",
                "studio": "Brickhouse NYC",
            }

            # IDs and metadata from data attributes (stable as long as Mindbody keeps these)
            cls["mindbody_session_id"] = session.get("id", "")
            cls["mindbody_class_id"] = session.get("data-bw-widget-mbo-class-id", "")
            cls["mindbody_class_name_slug"] = session.get("data-bw-widget-mbo-class-name", "")

            # Time
            start_el = session.select_one("time.hc_starttime")  # FRAGILE: time.hc_starttime
            end_el = session.select_one("time.hc_endtime")       # FRAGILE: time.hc_endtime
            if start_el:
                cls["start_time"] = start_el.get("datetime", "")
                cls["start_time_display"] = start_el.get_text(strip=True)
            if end_el:
                cls["end_time"] = end_el.get("datetime", "")
                cls["end_time_display"] = end_el.get_text(strip=True)

            # Duration (derive from start/end if present)
            if cls.get("start_time") and cls.get("end_time"):
                try:
                    fmt = "%Y-%m-%dT%H:%M"
                    t0 = datetime.strptime(cls["start_time"], fmt)
                    t1 = datetime.strptime(cls["end_time"], fmt)
                    cls["duration_minutes"] = int((t1 - t0).total_seconds() / 60)
                except ValueError:
                    pass

            # Class name
            name_el = session.select_one(".bw-session__name")  # FRAGILE: .bw-session__name
            cls["class_name"] = name_el.get_text(strip=True) if name_el else ""

            # Instructor — FRAGILE: .bw-session__staff
            instructor_el = session.select_one(".bw-session__staff")
            cls["instructor"] = instructor_el.get_text(strip=True) if instructor_el else ""

            # Location / room — FRAGILE: .bw-session__location
            location_el = session.select_one(".bw-session__location")
            cls["location"] = location_el.get_text(strip=True) if location_el else ""

            # Booking link — FRAGILE: .bw-widget__cta (Sign Up button) or .bw-widget__signup-now
            book_el = session.select_one("a.bw-widget__cta")
            if not book_el:
                book_el = session.select_one(".bw-widget__signup-now")
            cls["booking_url"] = book_el.get("href", "") if book_el else ""

            # Canceled flag — Mindbody always renders .bw-session__canceled in the static HTML
            # and hides it via an external stylesheet (not an inline style). We can't
            # distinguish hidden-by-CSS from visible-canceled in server-rendered markup,
            # so we conservatively mark nothing as canceled here.
            cls["is_canceled"] = False

            results.append(cls)

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def week_start_dates(num_weeks: int) -> list[str]:
    """Return YYYY-MM-DD strings for the Tuesday of the current + next N-1 weeks.

    Brickhouse uses Tuesday as its schedule week start (as observed in widget URLs).

    Special case: on Monday the Mindbody widget has rolled past the previous
    Tuesday's week, so we prepend today's date to capture today's classes.
    """
    today = date.today()
    # weekday(): Mon=0 … Sun=6; Tuesday=1
    days_since_tuesday = (today.weekday() - 1) % 7
    this_tuesday = today - __import__("datetime").timedelta(days=days_since_tuesday)
    dates = [
        (this_tuesday + __import__("datetime").timedelta(weeks=i)).isoformat()
        for i in range(num_weeks)
    ]
    # On Monday, this_tuesday is 6 days ago and the widget returns nothing for it.
    # Prepend today so we capture today's classes.
    if today.weekday() == 0:
        dates = [today.isoformat()] + dates
    return dates


def main():
    print("Fetching Brickhouse NYC schedule from Mindbody widget...")
    start_dates = week_start_dates(WEEKS_TO_FETCH)

    seen_ids: set[str] = set()
    all_classes: list[dict] = []

    for start_date in start_dates:
        data = fetch_load_markup(start_date)
        html = data.get("class_sessions", "")
        if not html:
            print(f"  Week {start_date}: empty response, skipping")
            continue

        week_classes = parse_classes(html)
        new = 0
        for cls in week_classes:
            sid = cls.get("mindbody_session_id", "")
            if sid and sid in seen_ids:
                continue
            if sid:
                seen_ids.add(sid)
            all_classes.append(cls)
            new += 1
        print(f"  Week {start_date}: {new} classes ({sum(1 for c in week_classes if c.get('is_canceled'))} canceled)")

    print(f"Total: {len(all_classes)} classes")

    output = {
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "studio": "Brickhouse NYC",
        "source_url": "https://brickhousedance.com/open-classes/",
        "endpoint_pattern": (
            f"https://widgets.mindbodyonline.com/widgets/schedules/{WIDGET_ID}/load_markup"
            "?callback=_cb&options%5Bstart_date%5D=YYYY-MM-DD&_=TIMESTAMP&mobile=false"
        ),
        "class_count": len(all_classes),
        "classes": all_classes,
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Saved to {OUTPUT_FILE}")

    # Print a sample non-canceled class
    non_canceled = [c for c in all_classes if not c.get("is_canceled")]
    sample = non_canceled[0] if non_canceled else (all_classes[0] if all_classes else None)
    if sample:
        print("\nSample class:")
        print(json.dumps({k: v for k, v in sample.items() if v is not None and v != ""}, indent=2))


if __name__ == "__main__":
    main()
