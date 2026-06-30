# NYC Dance Class Schedule Scraper — Findings

**Date of investigation:** 2026-06-30  
**Method:** Playwright headless browser (Chromium) to capture network traffic, then plain HTTP verification with `urllib.request`.

---

## Studio 1: Brickhouse NYC

**Schedule page:** https://brickhousedance.com/open-classes/  
**Booking platform:** Mindbody (studio ID 807568, widget token `5f43835d68c`)

### Phase 1 Result: ✅ Clean endpoint found — no browser needed for production

The page embeds a Healcode/Mindbody widget that makes two key JSONP calls after load:

| Request | URL Pattern | Content |
|---------|-------------|---------|
| Schedule HTML | `widgets.mindbodyonline.com/widgets/schedules/43835/load_markup?callback=_cb&options%5Bstart_date%5D=YYYY-MM-DD&_=TS&mobile=false` | **JSONP with full schedule as HTML** |
| Widget config | `widgets.mindbodyonline.com/widgets/schedules/5f43835d68c.json` | CSS/HTML shell, not class data |
| Store URL | `widgets.mindbodyonline.com/widgets/widget/5f43835d68c/store_deploy_url.json` | Returns "deactivated" error (ignore) |

**Chosen endpoint:** `load_markup` (JSONP, strips to JSON + HTML)

```
GET https://widgets.mindbodyonline.com/widgets/schedules/43835/load_markup
  ?callback=_cb
  &options%5Bstart_date%5D=YYYY-MM-DD   ← Tuesday of desired week (widget's week start)
  &_=<unix_ms_timestamp>
  &mobile=false
Headers:
  User-Agent: Mozilla/5.0 ...Chrome/124...
  Referer: https://brickhousedance.com/
```

**Response shape:**
```json
{
  "class_sessions": "<html string with .bw-session divs>",
  "calendar": "<html string for month calendar>",
  "filters": "{json string with available class types}"
}
```

The `class_sessions` HTML is parsed with BeautifulSoup. Key selectors:
- `.bw-widget__day` — day container (has `.bw-widget__date.date-YYYY-MM-DD` for stable date parsing)
- `.bw-session` — individual class (has `data-bw-widget-mbo-class-id`, `data-bw-widget-mbo-class-name` data attrs)
- `time.hc_starttime[datetime]`, `time.hc_endtime[datetime]` — ISO datetimes
- `.bw-session__name` — class name
- `.bw-session__staff` — instructor
- `.bw-session__location` — location/studio name
- `.bw-session__canceled` — present with "Cancelled" text when class is canceled
- `a.bw-widget__cta` — booking link (href)

### Auth / Bot protection
- Site uses Cloudflare (`/__challenge` 403 on first request, then auto-solved by the browser session). **Plain HTTP works without needing Cloudflare cookies** once you include a real `Referer` header — the widget endpoint is served from `widgets.mindbodyonline.com` (not the main Brickhouse domain), which has no Cloudflare protection.
- No API key, session token, or authentication required.
- No rate limiting observed on single-run testing.

### Stability notes
- Widget ID (`43835`) is embedded in the URL and unlikely to change unless Brickhouse switches platforms.
- The `options[start_date]` parameter controls which week is returned (use Tuesday as week start).
- If CSS class names (`.bw-session__name`, etc.) change, those selectors will need updating — search for `# FRAGILE` comments in `scrape_brickhouse.py`.

### Current data note
As of 2026-06-30, Brickhouse NYC has canceled all open classes for the weeks of June 30 and July 7 (July 4th holiday + Summer Intensive program). The scraper correctly reflects this via the `is_canceled` field. Classes will return when the intensive ends.

---

## Studio 2: Modega / Mover's Bodega

**Schedule page:** https://sutrapro.com/modega (Arketa / SutraPro platform)

### Phase 1 Result: ✅ Clean REST JSON endpoint found — no browser needed

SutraPro exposes a public widget API that returns structured JSON with full class data:

```
GET https://sutrapro.com/api/widget/data
  ?widgetName=modega
  &type=classes
  &start_time=<unix_timestamp>   ← Unix epoch of the desired week's Sunday midnight UTC
Headers:
  User-Agent: Mozilla/5.0 ...Chrome/124...
  Referer: https://sutrapro.com/
  Origin: https://sutrapro.com
```

**Response shape:**
```json
{
  "data": {
    "widget":   { "id": "...", "widgetName": "modega", ... },
    "classes":  [ { ...class object... }, ... ],   ← 240-250 items per week
    "offerings": null,
    "categories": null,
    ...
  }
}
```

Each class object contains: `class_name`, `start_time` (Unix epoch), `end_time` (Unix epoch), `instructor_name`, `location` (dict with `name`, `address`, lat/lng), `location_type`, `duration`, `max_capacity`, `total_booked`, `waitlistLength`, `isBookable`, `canceled`, `price`, `id` (bookable checkout link: `sutrapro.com/modega/checkout/<id>`), and more.

### Auth / Bot protection
- **No auth required.** No CORS restriction on direct fetch. No cookie or session needed.
- No rate limiting observed on single-run testing (fetching 4 weeks = 4 requests).
- No bot detection or CAPTCHA encountered.

### Pagination
The API returns ~250 classes per `start_time` (one week). Weeks appear to overlap slightly (recurring classes appear in multiple week responses). The scraper deduplicates by class ID.

### Stability notes
- `widgetName=modega` is stable as long as the studio stays on SutraPro.
- `start_time` should be the Unix timestamp of Sunday 00:00 UTC for the desired week.
- The response schema is clean REST JSON — no HTML parsing required.
- If the studio migrates off SutraPro, the entire endpoint changes. Consider monitoring `sutrapro.com/modega` for a redirect or 404.

---

## Summary

| Studio | Endpoint type | Browser needed? | Auth required? | Bot protection? | Fields available |
|--------|--------------|-----------------|----------------|-----------------|-----------------|
| Brickhouse NYC | Mindbody widget JSONP + HTML parsing | **No** | No | Cloudflare on main domain (not on widget CDN) | name, date, start/end time, duration, instructor, location, canceled status, booking link |
| Modega | SutraPro REST JSON | **No** | No | None observed | name, date, start/end time, duration, instructor, location+address, capacity, bookings, waitlist, price, booking link |

**Both studios can be scraped with plain HTTP — no Playwright needed in production.**

### Recommended cron schedule
- Run once per day (off-peak, e.g. 4 AM ET) to catch schedule changes.
- For Brickhouse, fetch current week + 1 week ahead (`WEEKS_TO_FETCH = 2`).
- For Modega, fetch current week + 3 weeks ahead (`WEEKS_TO_FETCH = 4`) to populate a full month view.

### Alternatives if endpoints break
- **Brickhouse:** Mindbody has a public Partner API (`api.mindbodyonline.com/public/v6`), but it requires an API key from Mindbody. Contact Brickhouse to request their public feed or a partner integration.
- **Modega:** Contact the studio directly for a calendar export (`.ics`) or ask SutraPro for a documented public API.
