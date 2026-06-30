#!/usr/bin/env python3
"""
Peridance Center — open class schedule scraper.

Data source: Mindbody/Healcode widget endpoint (plain HTTP, no browser required).
  https://widgets.mindbodyonline.com/widgets/schedules/143499/load_markup

Discovered via Playwright network capture on https://www.peridance.com/open-classes.
Same JSONP + HTML format as Brickhouse; identical CSS selectors apply.

Widget ID:    143499
Widget token: f9143499b7be  (for reference; not needed in load_markup call)
Studio site:  https://www.peridance.com/open-classes
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path

from bs4 import BeautifulSoup


# ── Config ─────────────────────────────────────────────────────────────────────

WIDGET_ID    = "143499"
WIDGET_TOKEN = "f9143499b7be"   # for reference only
WEEKS_TO_FETCH = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/javascript, application/javascript, */*; q=0.01",
    "Referer": "https://www.peridance.com/",
}

OUTPUT_FILE = Path(__file__).parent / "peridance_schedule.json"


# ── Fetch ──────────────────────────────────────────────────────────────────────

def load_markup_url(start_date: str) -> str:
    ts = int(time.time() * 1000)
    return (
        f"https://widgets.mindbodyonline.com/widgets/schedules/{WIDGET_ID}/load_markup"
        f"?callback=_cb&options%5Bstart_date%5D={start_date}&_={ts}&mobile=false"
    )

def fetch_load_markup(start_date: str) -> dict:
    url = load_markup_url(start_date)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode("utf-8", errors="replace")
    # Strip JSONP wrapper: _cb({...});
    json_str = re.sub(r"^[^(]+\(", "", raw).rstrip().rstrip(";").rstrip(")")
    return json.loads(json_str)


# ── Parse ──────────────────────────────────────────────────────────────────────

def parse_classes(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for day_div in soup.select(".bw-widget__day"):
        date_str = ""
        date_div = day_div.select_one(".bw-widget__date")
        if date_div:
            date_class = next(
                (c for c in date_div.get("class", []) if c.startswith("date-")), None
            )
            if date_class:
                date_str = date_class.replace("date-", "")
            else:
                date_text = date_div.get_text(strip=True)
                try:
                    dt = datetime.strptime(date_text, "%A, %B %d")
                    date_str = dt.strftime(f"{datetime.now().year}-%m-%d")
                except ValueError:
                    date_str = date_text

        for session in day_div.select(".bw-session"):
            cls = {
                "date":        date_str,
                "source_url":  "https://www.peridance.com/open-classes",
                "studio":      "Peridance",
            }

            cls["mindbody_session_id"]     = session.get("id", "")
            cls["mindbody_class_id"]       = session.get("data-bw-widget-mbo-class-id", "")
            cls["mindbody_class_name_slug"] = session.get("data-bw-widget-mbo-class-name", "")

            start_el = session.select_one("time.hc_starttime")
            end_el   = session.select_one("time.hc_endtime")
            if start_el:
                cls["start_time"]         = start_el.get("datetime", "")
                cls["start_time_display"] = start_el.get_text(strip=True)
            if end_el:
                cls["end_time"]           = end_el.get("datetime", "")
                cls["end_time_display"]   = end_el.get_text(strip=True)

            if cls.get("start_time") and cls.get("end_time"):
                try:
                    fmt = "%Y-%m-%dT%H:%M"
                    t0 = datetime.strptime(cls["start_time"], fmt)
                    t1 = datetime.strptime(cls["end_time"], fmt)
                    cls["duration_minutes"] = int((t1 - t0).total_seconds() / 60)
                except ValueError:
                    pass

            name_el       = session.select_one(".bw-session__name")
            instructor_el = session.select_one(".bw-session__staff")
            location_el   = session.select_one(".bw-session__location")
            book_el       = session.select_one("a.bw-widget__cta") or session.select_one(".bw-widget__signup-now")
            canceled_el   = session.select_one(".bw-session__canceled")

            cls["class_name"]  = name_el.get_text(strip=True)       if name_el       else ""
            cls["instructor"]  = instructor_el.get_text(strip=True)  if instructor_el else ""
            cls["location"]    = location_el.get_text(strip=True)    if location_el   else ""
            cls["booking_url"] = book_el.get("href", "")            if book_el       else ""
            cls["is_canceled"] = bool(canceled_el)

            results.append(cls)

    return results


# ── Week starts ────────────────────────────────────────────────────────────────

def week_start_dates(num_weeks: int) -> list:
    """Return YYYY-MM-DD strings for the Tuesday of the current + next N-1 weeks.
    Peridance uses the same Tuesday week-start as Brickhouse (confirmed from captured URL).
    """
    today = date.today()
    days_since_tuesday = (today.weekday() - 1) % 7  # Mon=0…Sun=6; Tue=1
    this_tuesday = today - timedelta(days=days_since_tuesday)
    return [
        (this_tuesday + timedelta(weeks=i)).isoformat()
        for i in range(num_weeks)
    ]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"Fetching Peridance schedule ({WEEKS_TO_FETCH} weeks)…")
    start_dates = week_start_dates(WEEKS_TO_FETCH)

    seen_ids: set = set()
    all_classes: list = []

    for start_date in start_dates:
        try:
            data = fetch_load_markup(start_date)
        except Exception as e:
            print(f"  Week {start_date}: fetch error — {e}", file=sys.stderr)
            continue

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

        canceled = sum(1 for c in week_classes if c.get("is_canceled"))
        print(f"  Week {start_date}: {new} classes ({canceled} canceled)")

    print(f"Total: {len(all_classes)} classes")

    output = {
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "studio": "Peridance",
        "source_url": "https://www.peridance.com/open-classes",
        "widget_id": WIDGET_ID,
        "endpoint_pattern": (
            f"https://widgets.mindbodyonline.com/widgets/schedules/{WIDGET_ID}/load_markup"
            "?callback=_cb&options%5Bstart_date%5D=YYYY-MM-DD&_=TIMESTAMP&mobile=false"
        ),
        "class_count": len(all_classes),
        "classes": all_classes,
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Saved to {OUTPUT_FILE}")

    non_canceled = [c for c in all_classes if not c.get("is_canceled")]
    sample = non_canceled[0] if non_canceled else (all_classes[0] if all_classes else None)
    if sample:
        print("\nSample class:")
        print(json.dumps({k: v for k, v in sample.items() if v is not None and v != ""}, indent=2))


if __name__ == "__main__":
    main()
