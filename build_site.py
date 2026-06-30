#!/usr/bin/env python3
"""
Build index.html — a mobile-optimized dance class schedule site.
Reads brickhouse_schedule.json and modega_schedule.json, normalises
the data, and bakes it into a single self-contained HTML file.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).parent


# ── helpers ──────────────────────────────────────────────────────────────────

ET = timezone(timedelta(hours=-4))  # EDT (summer)

def parse_dt(iso: str):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=ET)
        return dt.astimezone(ET)
    except Exception:
        return None

def fmt_time(dt) -> str:
    if not dt:
        return ""
    return dt.strftime("%-I:%M %p")

def fmt_date_key(dt, date_str: str) -> str:
    if dt:
        return dt.strftime("%Y-%m-%d")
    return date_str[:10] if date_str else ""

def extract_level(name: str) -> str:
    n = name.lower()
    if any(x in n for x in ["adv. beg", "adv beg", "beg./adv"]):
        return "Beginner"
    if any(x in n for x in ["beginner", "beg."]):
        return "Beginner"
    if any(x in n for x in ["all levels", "open level", "open hip", "open break",
                              "open wav", "open free", "open mod"]):
        return "All Levels"
    if any(x in n for x in ["int./adv", "int/adv"]):
        return "Int/Adv"
    if any(x in n for x in ["intermediate", "int."]):
        return "Intermediate"
    if any(x in n for x in ["advanced", "adv."]):
        return "Advanced"
    return "All Levels"

def start_hour(dt) -> float:
    if not dt:
        return -1
    return dt.hour + dt.minute / 60


# ── load + normalise ──────────────────────────────────────────────────────────

def load_brickhouse():
    raw = json.loads((HERE / "brickhouse_schedule.json").read_text())
    out = []
    for c in raw["classes"]:
        start_dt = parse_dt(c.get("start_time", ""))
        end_dt   = parse_dt(c.get("end_time", ""))
        name = c.get("class_name", "")
        parts = re.split(r"\s*[-–]\s*", name, maxsplit=1)
        display_name = parts[-1].strip() if len(parts) > 1 else name.strip()
        category = parts[0].strip() if len(parts) > 1 else ""
        out.append({
            "studio":        "Brickhouse NYC",
            "studio_key":    "brickhouse",
            "class_name":    display_name,
            "category":      category,
            "instructor":    c.get("instructor", ""),
            "date_key":      fmt_date_key(start_dt, c.get("date", "")),
            "start_dt":      start_dt,
            "start_display": fmt_time(start_dt) or c.get("start_time_display", ""),
            "end_display":   fmt_time(end_dt) or c.get("end_time_display", ""),
            "duration_min":  c.get("duration_minutes"),
            "level":         extract_level(name),
            "start_hour":    start_hour(start_dt),
            "is_canceled":   c.get("is_canceled", False),
            "booking_url":   c.get("source_url", "https://brickhousedance.com/open-classes/"),
            "max_capacity":  None,
            "total_booked":  None,
            "description":   "",
        })
    return out

def load_modega():
    raw = json.loads((HERE / "modega_schedule.json").read_text())
    out = []
    for c in raw["classes"]:
        start_dt = parse_dt(c.get("start_time", ""))
        end_dt   = parse_dt(c.get("end_time", ""))
        name = c.get("class_name", "")
        out.append({
            "studio":        "Modega",
            "studio_key":    "modega",
            "class_name":    name,
            "category":      "",
            "instructor":    c.get("instructor", ""),
            "date_key":      fmt_date_key(start_dt, c.get("date", "")),
            "start_dt":      start_dt,
            "start_display": fmt_time(start_dt),
            "end_display":   fmt_time(end_dt),
            "duration_min":  c.get("duration_minutes"),
            "level":         extract_level(name),
            "start_hour":    start_hour(start_dt),
            "is_canceled":   c.get("is_canceled", False),
            "booking_url":   c.get("booking_url", c.get("source_url", "")),
            "max_capacity":  c.get("max_capacity"),
            "total_booked":  c.get("total_booked"),
            "description":   c.get("description", ""),
        })
    return out

def load_peridance():
    p = HERE / "peridance_schedule.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    out = []
    for c in raw.get("classes", []):
        start_dt = parse_dt(c.get("start_time", ""))
        end_dt   = parse_dt(c.get("end_time", ""))
        name = c.get("class_name", "")
        out.append({
            "studio":        "Peridance",
            "studio_key":    "peridance",
            "class_name":    name,
            "category":      c.get("category", ""),
            "instructor":    c.get("instructor", ""),
            "date_key":      fmt_date_key(start_dt, c.get("date", "")),
            "start_dt":      start_dt,
            "start_display": fmt_time(start_dt),
            "end_display":   fmt_time(end_dt),
            "duration_min":  c.get("duration_minutes"),
            "level":         extract_level(name),
            "start_hour":    start_hour(start_dt),
            "is_canceled":   c.get("is_canceled", False),
            "booking_url":   c.get("booking_url", "https://peridance.org"),
            "max_capacity":  c.get("max_capacity"),
            "total_booked":  c.get("total_booked"),
            "description":   c.get("description", ""),
        })
    return out

def to_js_obj(classes) -> str:
    serialisable = []
    for c in classes:
        d = dict(c)
        d["start_dt"] = d["start_dt"].isoformat() if d["start_dt"] else ""
        serialisable.append(d)
    return json.dumps(serialisable, ensure_ascii=False)


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<meta name="theme-color" content="#ddb5c8"/>
<title>NYC Dance</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700&family=Permanent+Marker&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;width:100%}
html{-webkit-text-size-adjust:100%;background:#ddb5c8}
body{
  font-family:'Inter',system-ui,-apple-system,sans-serif;
  background:#eceae6;
  overscroll-behavior-y:none;
  display:flex;justify-content:center;
}
button{cursor:pointer;font-family:inherit;border:none;background:none;color:inherit}
a{color:inherit;text-decoration:none}

/* ── app shell — full bleed on mobile, max-width on desktop ── */
.app-shell{
  width:100%;
  /* on larger screens cap at 390px so it looks like a phone; on mobile fill edge-to-edge */
  max-width:390px;
  /* use dvh so Safari's collapsing URL bar is accounted for */
  height:100dvh;
  height:100svh; /* fallback for older Safari */
  background:#eceae6;
  position:relative;
  display:flex;flex-direction:column;
  overflow:hidden;
}
/* on real phones (≤430px) go fully edge-to-edge */
@media (max-width:430px){
  .app-shell{max-width:100%}
  body{background:#eceae6}
}

/* ── full-shell background layers (don't scroll) ── */
.bg-radial{
  position:absolute;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 70% 45% at 85% 2%, rgba(208,120,155,0.60) 0%, transparent 100%);
}
.bg-dots{
  position:absolute;inset:0;pointer-events:none;z-index:0;
  opacity:0.32;
  background-image:radial-gradient(circle, rgba(0,0,0,.28) 1px, transparent 1px);
  background-size:2.5px 2.5px;
}

/* ── header (not scrollable, sits above main-scroll in flex column) ── */
.cal-header{
  flex-shrink:0;
  padding:calc(env(safe-area-inset-top) + 20px) 18px 0;
  position:relative;z-index:10;
  user-select:none;
}
.cal-header-inner{position:relative;z-index:1}

/* row 1: location + action buttons */
.header-row1{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:10px;
}
.location-label{
  font-size:12px;font-weight:500;letter-spacing:.07em;
  color:#1a1a18;text-transform:uppercase;
}
.header-actions{display:flex;align-items:center;gap:6px}
.icon-btn{
  width:30px;height:30px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  background:rgba(255,255,255,.45);
  border:0.5px solid rgba(26,26,24,.10);
  transition:background .15s;
  -webkit-tap-highlight-color:transparent;
}
.icon-btn:active{background:rgba(255,255,255,.75)}
.icon-btn svg{width:15px;height:15px;stroke:#1a1a18;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}

/* row 2: title + updated */
.header-row2{
  display:flex;align-items:baseline;justify-content:space-between;
  margin-bottom:16px;
}
.page-title{font-family:'Permanent Marker',cursive;font-size:28px;font-weight:400;color:#111;line-height:1.1;letter-spacing:.5px}
.updated-text{font-family:'DM Mono',monospace;font-size:10px;color:#8c8a82;font-weight:400;letter-spacing:.02em}

/* ── week strip ── */
.week-strip{
  flex:1;display:flex;
  overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;
  padding:6px 0 14px;gap:2px;
}
.week-strip::-webkit-scrollbar{display:none}

.day-col{
  flex:1;min-width:42px;
  display:flex;flex-direction:column;align-items:center;gap:3px;
  padding:6px 4px 6px;border-radius:8px;
  cursor:pointer;-webkit-tap-highlight-color:transparent;
  transition:background .18s;
}
.day-col.selected{background:#1a1a18}
.day-letter{font-size:10px;font-weight:500;color:#6e6c66;text-transform:uppercase;letter-spacing:.04em}
.day-col.selected .day-letter{color:rgba(236,234,230,.65)}
.day-num{font-family:'DM Mono',monospace;font-size:13px;font-weight:500;color:#1a1a18}
.day-col.selected .day-num{color:#eceae6}
.day-col.today:not(.selected) .day-num{color:#d4537e}
.day-dot{width:4px;height:4px;border-radius:50%;background:#d4537e;opacity:0;transition:opacity .2s;margin-top:1px}
.day-col.has-classes .day-dot{opacity:1}
.day-col.selected .day-dot{background:rgba(236,234,230,.55)}


/* ── main scroll — transparent so bg shows through ── */
.main-scroll{
  flex:1;min-height:0;
  overflow-y:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;
  padding:8px 16px calc(72px + env(safe-area-inset-bottom));
  position:relative;z-index:1;
}
.main-scroll::-webkit-scrollbar{display:none}

/* section dividers */
.section-divider{
  display:flex;align-items:center;gap:8px;
  font-size:11px;font-weight:500;letter-spacing:.05em;
  color:#9a9688;text-transform:uppercase;
  margin:8px 0 8px;
}
.section-divider:first-child{margin-top:2px}
.section-line{flex:1;height:0.5px;background:rgba(26,26,24,.16)}

/* empty state */
.empty-state{text-align:center;padding:52px 20px}
.empty-icon{font-size:44px;margin-bottom:14px}
.empty-title{font-size:17px;font-weight:600;color:#1a1a18;margin-bottom:6px}
.empty-sub{font-size:13px;color:#9a9688;line-height:1.55}

/* ── cards ── */
.card{
  border-radius:14px;overflow:hidden;margin-bottom:10px;
  position:relative;
  transition:transform .15s;
  animation:slideUp .22s ease both;
}
.card:active{transform:scale(.985)}
@keyframes slideUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* Brickhouse — warm darks */
.card-bh-0{background:linear-gradient(155deg,#2c2926 0%,#161411 72%);background-image:repeating-linear-gradient(60deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 6px),linear-gradient(155deg,#2c2926 0%,#161411 72%)}
.card-bh-1{background:linear-gradient(155deg,#3a2222 0%,#1d0f0f 72%);background-image:repeating-linear-gradient(115deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#3a2222 0%,#1d0f0f 72%)}
.card-bh-2{background:linear-gradient(155deg,#282232 0%,#120e18 72%);background-image:repeating-linear-gradient(35deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#282232 0%,#120e18 72%)}
/* Modega — cool darks */
.card-mod-0{background:linear-gradient(155deg,#30293a 0%,#14101e 72%);background-image:repeating-linear-gradient(135deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#30293a 0%,#14101e 72%)}
.card-mod-1{background:linear-gradient(155deg,#1c2a38 0%,#0c131c 72%);background-image:repeating-linear-gradient(80deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#1c2a38 0%,#0c131c 72%)}
.card-mod-2{background:linear-gradient(155deg,#1e3228 0%,#0d1812 72%);background-image:repeating-linear-gradient(18deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#1e3228 0%,#0d1812 72%)}
/* Peridance — blue-navy darks */
.card-per-0{background:linear-gradient(155deg,#1e2840 0%,#0c1020 72%);background-image:repeating-linear-gradient(50deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#1e2840 0%,#0c1020 72%)}
.card-per-1{background:linear-gradient(155deg,#28203c 0%,#120e1e 72%);background-image:repeating-linear-gradient(100deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#28203c 0%,#120e1e 72%)}
.card-per-2{background:linear-gradient(155deg,#24302e 0%,#101814 72%);background-image:repeating-linear-gradient(160deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 6px),linear-gradient(155deg,#24302e 0%,#101814 72%)}

.card-canceled{opacity:.48}

.card-inner{padding:14px;position:relative;z-index:1}

.card-top-row{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
/* pill now shows TIME */
.time-pill{font-family:'DM Mono',monospace;background:#fff;color:#1a1a18;font-size:11px;font-weight:500;padding:3px 11px;border-radius:20px;letter-spacing:.01em}
.save-btn{
  color:rgba(232,228,220,.55);line-height:1;padding:0;
  transition:color .15s;
}
.save-btn:active{color:rgba(232,228,220,.9)}
.save-btn svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
/* level label below pill */
.card-level{font-size:10px;font-weight:500;color:rgba(216,212,204,.7);text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px}
.card-name{font-family:'DM Sans',sans-serif;color:#fff;font-size:19px;font-weight:500;line-height:1.2;margin-bottom:10px}
.card-instructor-row{display:flex;align-items:center;gap:6px}
.small-avatar{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:9px;color:#fff;font-weight:500}
.card-instructor-name{color:#b5b1a6;font-size:12px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* capacity micro-bar (Modega real data only) */
.cap-wrap{margin-top:10px}
.cap-bar-bg{height:2px;background:rgba(255,255,255,.12);border-radius:1px}
.cap-bar-fill{height:2px;border-radius:1px;background:rgba(255,255,255,.42)}
.cap-text{font-family:'DM Mono',monospace;font-size:10px;color:rgba(232,228,220,.48);margin-top:4px;letter-spacing:.02em}

/* invisible booking tap layer */
.card-tap{position:absolute;inset:0;z-index:2}

/* ── bottom nav ── */
.bottom-nav{
  position:absolute;bottom:0;left:0;right:0;
  display:flex;justify-content:space-around;
  padding:10px 0 calc(14px + env(safe-area-inset-bottom));
  background:rgba(236,234,230,.95);
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border-top:0.5px solid rgba(26,26,24,.10);
  z-index:50;
}
.nav-item{
  display:flex;flex-direction:column;align-items:center;gap:3px;
  cursor:pointer;-webkit-tap-highlight-color:transparent;padding:0 18px;
}
.nav-icon svg{width:22px;height:22px;stroke:#9a9688;fill:none;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;transition:stroke .15s}
.nav-label{font-size:10px;color:#9a9688;font-weight:500;transition:color .15s}
.nav-item.active .nav-icon svg{stroke:#1a1a18}
.nav-item.active .nav-label{color:#1a1a18;font-weight:600}

/* ── drawer overlay ── */
.drawer-overlay{position:fixed;inset:0;z-index:200;background:rgba(26,26,24,0);pointer-events:none;transition:background .3s}
.drawer-overlay.open{background:rgba(26,26,24,.5);pointer-events:all}

/* ── filter drawer ── */
.drawer{
  position:fixed;bottom:0;left:50%;transform:translateX(-50%) translateY(100%);
  width:100%;max-width:390px;z-index:201;
  background:#fff;border-radius:24px 24px 0 0;
  padding:0 0 calc(20px + env(safe-area-inset-bottom));
  transition:transform .35s cubic-bezier(.32,1,.36,1);
  max-height:92svh;display:flex;flex-direction:column;
}
.drawer.open{transform:translateX(-50%) translateY(0)}
.drawer-handle{width:40px;height:4px;border-radius:2px;background:#e0dbd6;margin:12px auto 0;flex-shrink:0}
.drawer-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px 10px;flex-shrink:0}
.drawer-title{font-size:18px;font-weight:700;color:#1a1a18}
.drawer-close{width:32px;height:32px;border-radius:50%;background:#f2f0ec;display:flex;align-items:center;justify-content:center;font-size:15px;color:#6e6c66}
.drawer-scroll{overflow-y:auto;flex:1;padding:0 20px;scrollbar-width:none}
.drawer-scroll::-webkit-scrollbar{display:none}
.fsection{margin-bottom:22px}
.fsection-label{font-size:11px;font-weight:600;color:#9a9688;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px}
.fchip-row{display:flex;flex-wrap:wrap;gap:8px}
.fchip{padding:8px 15px;border-radius:20px;font-size:13px;font-weight:500;color:#3a3830;background:#f0ece6;border:1.5px solid transparent;transition:all .15s}
.fchip.active{background:#1a1a18;color:#eceae6;border-color:#1a1a18}
.teacher-chip-row{display:flex;flex-wrap:wrap;gap:6px}
.tchip{padding:7px 13px;border-radius:18px;font-size:12px;font-weight:500;color:#3a3830;background:#f0ece6;border:1.5px solid transparent;transition:all .15s}
.tchip.active{background:#1a1a18;color:#eceae6}
.time-display-row{display:flex;justify-content:space-between;font-size:13px;font-weight:600;color:#1a1a18;margin-bottom:12px}
.time-display-row span{background:#f0ece6;padding:5px 12px;border-radius:10px;min-width:86px;text-align:center}
.range-slider-wrap{position:relative;height:32px;margin:0 4px}
.slider-track-bg{position:absolute;top:50%;left:0;right:0;height:4px;background:#e8e4de;border-radius:2px;transform:translateY(-50%)}
.slider-track-fill{position:absolute;top:50%;height:4px;background:#1a1a18;border-radius:2px;transform:translateY(-50%)}
.range-slider-wrap input[type=range]{position:absolute;top:50%;width:100%;transform:translateY(-50%);-webkit-appearance:none;appearance:none;background:transparent;pointer-events:none;margin:0}
.range-slider-wrap input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:24px;height:24px;border-radius:50%;background:#fff;border:2.5px solid #1a1a18;box-shadow:0 2px 8px rgba(0,0,0,.14);pointer-events:all;cursor:grab}
.range-slider-wrap input[type=range]::-moz-range-thumb{width:24px;height:24px;border-radius:50%;background:#fff;border:2.5px solid #1a1a18;box-shadow:0 2px 8px rgba(0,0,0,.14);pointer-events:all;cursor:grab}
.drawer-footer{padding:14px 20px 0;flex-shrink:0}
.apply-btn{display:block;width:100%;padding:15px;border-radius:14px;background:#1a1a18;color:#eceae6;font-size:15px;font-weight:600;text-align:center;transition:opacity .15s;letter-spacing:.01em}
.apply-btn:active{opacity:.78}
</style>
</head>
<body>
<div class="app-shell">

  <!-- fixed background layers -->
  <div class="bg-radial"></div>
  <div class="bg-dots"></div>

  <!-- header (stays put; main-scroll scrolls below it) -->
  <header class="cal-header">
    <div class="cal-header-inner">

      <!-- row 1: location + action icons -->
      <div class="header-row1">
        <span class="location-label">New York City</span>
        <div class="header-actions">
          <button class="icon-btn" id="filterBtn" title="Filters">
            <svg viewBox="0 0 16 16"><path d="M2 4h12M5 8h6M7 12h2"/></svg>
          </button>
          <button class="icon-btn" id="savedBtn" title="Saved">
            <svg viewBox="0 0 16 16"><path d="M3 2h10a1 1 0 0 1 1 1v11l-5-3-5 3V3a1 1 0 0 1 1-1z"/></svg>
          </button>
        </div>
      </div>

      <!-- row 2: title + updated -->
      <div class="header-row2">
        <h1 class="page-title" id="pageTitle">July</h1>
        <span class="updated-text" id="updatedText">Updated today</span>
      </div>

      <!-- week strip -->
      <div class="week-strip" id="weekStrip"></div>

    </div>
  </header>

  <!-- scrollable classes — transparent so bg shows through -->
  <main class="main-scroll" id="mainScroll">
    <div id="classesList"></div>
  </main>

  <!-- bottom nav -->
  <nav class="bottom-nav">
    <div class="nav-item active" id="scheduleNav">
      <div class="nav-icon">
        <svg viewBox="0 0 22 22"><rect x="3" y="4" width="16" height="15" rx="2"/><path d="M7 2v4M15 2v4M3 9h16"/></svg>
      </div>
      <span class="nav-label">Schedule</span>
    </div>
    <div class="nav-item" id="popupNav">
      <div class="nav-icon">
        <svg viewBox="0 0 22 22"><path d="M11 3v18M3 8l8-5 8 5"/><rect x="5" y="11" width="12" height="10" rx="1"/></svg>
      </div>
      <span class="nav-label">Pop up</span>
    </div>
    <div class="nav-item" id="savedNav">
      <div class="nav-icon">
        <svg viewBox="0 0 22 22"><path d="M5 3h12a1 1 0 0 1 1 1v15l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg>
      </div>
      <span class="nav-label">Saved</span>
    </div>
  </nav>

</div><!-- /app-shell -->

<!-- drawer overlay -->
<div class="drawer-overlay" id="drawerOverlay"></div>

<!-- filter drawer -->
<div class="drawer" id="drawer">
  <div class="drawer-handle"></div>
  <div class="drawer-header">
    <span class="drawer-title">Filters</span>
    <button class="drawer-close" id="drawerClose">✕</button>
  </div>
  <div class="drawer-scroll">

    <div class="fsection">
      <div class="fsection-label">Studio</div>
      <div class="fchip-row">
        <button class="fchip active" data-group="studio" data-val="all">All</button>
        <button class="fchip" data-group="studio" data-val="brickhouse">Brickhouse NYC</button>
        <button class="fchip" data-group="studio" data-val="modega">Modega</button>
        <button class="fchip" data-group="studio" data-val="peridance">Peridance</button>
      </div>
    </div>

    <div class="fsection">
      <div class="fsection-label">Level</div>
      <div class="fchip-row">
        <button class="fchip active" data-group="level" data-val="all">All</button>
        <button class="fchip" data-group="level" data-val="Beginner">Beginner</button>
        <button class="fchip" data-group="level" data-val="All Levels">Open</button>
        <button class="fchip" data-group="level" data-val="Intermediate">Intermediate</button>
        <button class="fchip" data-group="level" data-val="Int/Adv">Int/Adv</button>
        <button class="fchip" data-group="level" data-val="Advanced">Advanced</button>
      </div>
    </div>

    <div class="fsection">
      <div class="fsection-label">Time of Day</div>
      <div class="time-display-row">
        <span id="timeStartLabel">6:00 AM</span>
        <span id="timeEndLabel">12:00 AM</span>
      </div>
      <div class="range-slider-wrap">
        <div class="slider-track-bg"></div>
        <div class="slider-track-fill" id="sliderFill"></div>
        <input type="range" id="rangeMin" min="6" max="24" step="0.5" value="6"/>
        <input type="range" id="rangeMax" min="6" max="24" step="0.5" value="24"/>
      </div>
    </div>

    <div class="fsection">
      <div class="fsection-label">Teacher</div>
      <div class="teacher-chip-row" id="teacherChipRow"></div>
    </div>

  </div>
  <div class="drawer-footer">
    <button class="apply-btn" id="applyBtn">Show classes</button>
  </div>
</div>

<script>
// ── data ──
const ALL_CLASSES = __ALL_CLASSES__;

// ── state ──
const S = {weekOffset:0, selectedDate:'', studio:'all', level:'all', teacher:'all', timeMin:6, timeMax:24};

const BH_STYLES  = ['card-bh-0','card-bh-1','card-bh-2'];
const MOD_STYLES = ['card-mod-0','card-mod-1','card-mod-2'];
const PER_STYLES = ['card-per-0','card-per-1','card-per-2'];

const AV_COLORS = ['#639922','#534ab7','#1d9e75','#d4537e','#ba7517','#2a6cb5','#9e4a20','#7b5ea7','#c05a3c','#1f8e8e'];
function avatarColor(name){if(!name)return'#888';let h=0;for(const c of name)h=(h*31+c.charCodeAt(0))>>>0;return AV_COLORS[h%AV_COLORS.length]}
function initials(name){if(!name)return'?';const p=name.trim().split(/\s+/);return p.length===1?p[0].slice(0,2).toUpperCase():(p[0][0]+p[p.length-1][0]).toUpperCase()}
function fmtHour(h){if(h>=24)return'12:00 AM';const hr=Math.floor(h),mn=Math.round((h-hr)*60),period=hr>=12?'PM':'AM',dh=hr>12?hr-12:(hr===0?12:hr);return`${dh}:${mn.toString().padStart(2,'0')} ${period}`}

const DAY_LETTERS=['SUN','MON','TUE','WED','THU','FRI','SAT'];
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];

function todayKey(){const d=new Date();return isoKey(d)}
function isoKey(d){return`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
function weekStartDate(off){const d=new Date();d.setHours(0,0,0,0);d.setDate(d.getDate()-d.getDay()+off*7);return d}
function addDays(d,n){const r=new Date(d);r.setDate(r.getDate()+n);return r}

function filteredForDate(dateKey){
  return ALL_CLASSES.filter(c=>{
    if(c.date_key!==dateKey)return false;
    if(S.studio!=='all'&&c.studio_key!==S.studio)return false;
    if(S.level!=='all'&&c.level!==S.level)return false;
    if(S.teacher!=='all'&&c.instructor!==S.teacher)return false;
    const h=c.start_hour;if(h<0)return true;
    return h>=S.timeMin&&h<=S.timeMax;
  });
}
function datesWithClasses(){
  const s=new Set();
  ALL_CLASSES.forEach(c=>{if(!c.is_canceled&&matchesFilters(c))s.add(c.date_key)});
  return s;
}
function matchesFilters(c){
  if(S.studio!=='all'&&c.studio_key!==S.studio)return false;
  if(S.level!=='all'&&c.level!==S.level)return false;
  if(S.teacher!=='all'&&c.instructor!==S.teacher)return false;
  const h=c.start_hour;if(h>=0&&(h<S.timeMin||h>S.timeMax))return false;
  return true;
}

// ── render calendar ──
function renderCalendar(){
  const strip=document.getElementById('weekStrip');
  const start=weekStartDate(S.weekOffset);
  const dotDates=datesWithClasses();
  const today=todayKey();
  const mid=addDays(start,3);
  // update header title to show current month
  document.getElementById('pageTitle').textContent=MONTHS[mid.getMonth()];
  strip.innerHTML='';
  for(let i=0;i<7;i++){
    const d=addDays(start,i);
    const key=isoKey(d);
    const col=document.createElement('div');
    col.className='day-col'
      +(key===S.selectedDate?' selected':'')
      +(key===today?' today':'')
      +(dotDates.has(key)?' has-classes':'');
    col.innerHTML=`
      <span class="day-letter">${DAY_LETTERS[d.getDay()]}</span>
      <span class="day-num">${d.getDate()}</span>
      <span class="day-dot"></span>`;
    col.addEventListener('click',()=>{S.selectedDate=key;renderAll()});
    strip.appendChild(col);
  }
}

// ── render classes ──
function renderClasses(){
  const listEl=document.getElementById('classesList');
  if(!S.selectedDate){listEl.innerHTML='';return}
  const classes=filteredForDate(S.selectedDate);
  if(!classes.length){
    listEl.innerHTML=`<div class="empty-state"><div class="empty-icon">🕺</div><div class="empty-title">No classes this day</div><div class="empty-sub">Try different filters or pick another day.</div></div>`;
    return;
  }
  classes.sort((a,b)=>a.start_hour-b.start_hour);
  listEl.innerHTML='';
  let lastSec='';
  classes.forEach((c,i)=>{
    const sec=timeSection(c.start_hour);
    if(sec!==lastSec){
      const div=document.createElement('div');
      div.className='section-divider';
      div.innerHTML=`${sec}<div class="section-line"></div>`;
      listEl.appendChild(div);
      lastSec=sec;
    }
    listEl.appendChild(buildCard(c,i));
  });
}

function timeSection(h){if(h<0||h<12)return'Morning';if(h<17)return'Afternoon';return'Evening'}

function buildCard(c,i){
  const div=document.createElement('div');
  let sv=0;{let h=0;for(const ch of(c.class_name||''))h=(h*31+ch.charCodeAt(0))>>>0;sv=h%3}
  const styleClass=c.studio_key==='brickhouse'?BH_STYLES[sv]:c.studio_key==='peridance'?PER_STYLES[sv]:MOD_STYLES[sv];
  div.className=`card ${styleClass}${c.is_canceled?' card-canceled':''}`;
  div.style.animationDelay=`${Math.min(i*35,200)}ms`;

  const color=avatarColor(c.instructor);
  const abbr=initials(c.instructor);
  const levelLabel=c.level||'Open';
  const timeStr=c.start_display?(c.end_display?`${c.start_display} – ${c.end_display}`:c.start_display):'';

  // capacity: only show when both values are real and max > 0
  let capHTML='';
  if(c.max_capacity>0&&c.total_booked!=null){
    const pct=Math.min(100,Math.round(c.total_booked/c.max_capacity*100));
    const spots=c.max_capacity-c.total_booked;
    const capText=spots<=0?'Full':spots<=5?`${spots} spots left`:`${c.total_booked} / ${c.max_capacity} booked`;
    capHTML=`<div class="cap-wrap"><div class="cap-bar-bg"><div class="cap-bar-fill" style="width:${pct}%"></div></div><div class="cap-text">${capText}</div></div>`;
  }

  const bookHref=c.booking_url&&!c.is_canceled
    ?`<a href="${esc(c.booking_url)}" target="_blank" rel="noopener" class="card-tap" aria-label="Book ${esc(c.class_name)}"></a>`:'';

  div.innerHTML=`${bookHref}
    <div class="card-inner">
      <div class="card-top-row">
        <span class="time-pill">${esc(timeStr||'—')}</span>
        <button class="save-btn" aria-label="Save">
          <svg viewBox="0 0 16 16"><path d="M3 2h10a1 1 0 0 1 1 1v11l-5-3-5 3V3a1 1 0 0 1 1-1z"/></svg>
        </button>
      </div>
      <div class="card-level">${esc(levelLabel)}</div>
      <div class="card-name">${esc(c.class_name)}</div>
      <div class="card-instructor-row">
        <div class="small-avatar" style="background:${color}">${abbr}</div>
        <span class="card-instructor-name">${esc(c.instructor||'—')}</span>
      </div>
      ${capHTML}
    </div>`;
  return div;
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

// ── drawer ──
function openDrawer(){
  document.getElementById('drawerOverlay').classList.add('open');
  document.getElementById('drawer').classList.add('open');
  document.body.style.overflow='hidden';
  buildTeacherChips();updateApplyBtn();
}
function closeDrawer(){
  document.getElementById('drawerOverlay').classList.remove('open');
  document.getElementById('drawer').classList.remove('open');
  document.body.style.overflow='';
}

function buildTeacherChips(){
  const row=document.getElementById('teacherChipRow');
  const teachers=[...new Set(
    ALL_CLASSES
      .filter(c=>S.studio==='all'||c.studio_key===S.studio)
      .filter(c=>c.instructor&&!c.instructor.includes('LLC')&&c.instructor!=='Various *'&&c.instructor!=='Modega')
      .map(c=>c.instructor)
  )].sort();
  row.innerHTML='';
  const allChip=document.createElement('button');
  allChip.className='tchip'+(S.teacher==='all'?' active':'');
  allChip.textContent='All teachers';
  allChip.addEventListener('click',()=>{S.teacher='all';row.querySelectorAll('.tchip').forEach(c=>c.classList.remove('active'));allChip.classList.add('active');updateApplyBtn()});
  row.appendChild(allChip);
  teachers.forEach(t=>{
    const chip=document.createElement('button');
    chip.className='tchip'+(S.teacher===t?' active':'');chip.textContent=t;
    chip.addEventListener('click',()=>{S.teacher=t;row.querySelectorAll('.tchip').forEach(c=>c.classList.remove('active'));chip.classList.add('active');updateApplyBtn()});
    row.appendChild(chip);
  });
}

function updateSlider(){
  const lo=parseFloat(document.getElementById('rangeMin').value);
  const hi=parseFloat(document.getElementById('rangeMax').value);
  const[a,b]=[Math.min(lo,hi),Math.max(lo,hi)];
  S.timeMin=a;S.timeMax=b;
  const pLo=((a-6)/18)*100,pHi=((b-6)/18)*100;
  document.getElementById('sliderFill').style.left=pLo+'%';
  document.getElementById('sliderFill').style.width=(pHi-pLo)+'%';
  document.getElementById('timeStartLabel').textContent=fmtHour(a);
  document.getElementById('timeEndLabel').textContent=fmtHour(b);
  updateApplyBtn();
}
function updateApplyBtn(){const n=filteredForDate(S.selectedDate).length;document.getElementById('applyBtn').textContent=`Show ${n} class${n!==1?'es':''}`}

document.querySelectorAll('.fchip').forEach(chip=>{
  chip.addEventListener('click',()=>{
    const group=chip.dataset.group,val=chip.dataset.val;
    chip.closest('.fchip-row').querySelectorAll('.fchip').forEach(c=>c.classList.remove('active'));
    chip.classList.add('active');
    if(group==='studio'){S.studio=val;buildTeacherChips()}
    if(group==='level')S.level=val;
    updateApplyBtn();
  });
});
document.getElementById('rangeMin').addEventListener('input',updateSlider);
document.getElementById('rangeMax').addEventListener('input',updateSlider);
document.getElementById('filterBtn').addEventListener('click',openDrawer);
document.getElementById('savedBtn').addEventListener('click',()=>{
  // bookmark button in header — same as saved tab
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('savedNav').classList.add('active');
});
document.getElementById('drawerClose').addEventListener('click',closeDrawer);
document.getElementById('drawerOverlay').addEventListener('click',closeDrawer);
document.getElementById('applyBtn').addEventListener('click',()=>{closeDrawer();renderAll()});

// nav tabs
['scheduleNav','popupNav','savedNav'].forEach(id=>{
  document.getElementById(id).addEventListener('click',()=>{
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    if(id==='popupNav') openDrawer();
    if(id==='scheduleNav') renderAll();
  });
});

function renderAll(){renderCalendar();renderClasses()}

// ── init ──
(function init(){
  const today=todayKey();
  const allDates=[...new Set(ALL_CLASSES.filter(c=>!c.is_canceled).map(c=>c.date_key))].sort();
  const future=allDates.filter(d=>d>=today);
  S.selectedDate=future.length?future[0]:allDates[allDates.length-1];
  const[sy,sm,sd]=S.selectedDate.split('-').map(Number);
  const selDate=new Date(sy,sm-1,sd);
  const todayDate=new Date();todayDate.setHours(0,0,0,0);
  const todaySunday=new Date(todayDate);todaySunday.setDate(todaySunday.getDate()-todayDate.getDay());
  const selSunday=new Date(selDate);selSunday.setDate(selSunday.getDate()-selDate.getDay());
  S.weekOffset=Math.round((selSunday-todaySunday)/(7*86400000));
  updateSlider();buildTeacherChips();renderAll();
})();
</script>
</body>
</html>
"""


# ── combine + emit ────────────────────────────────────────────────────────────

def main():
    bh  = load_brickhouse()
    md  = load_modega()
    per = load_peridance()
    all_classes = sorted(
        bh + md + per,
        key=lambda c: (c["date_key"], c["start_hour"] if c["start_hour"] >= 0 else 99)
    )

    js_data = to_js_obj(all_classes)
    html = HTML.replace("__ALL_CLASSES__", js_data)

    out = HERE / "index.html"
    out.write_text(html)
    size_kb = out.stat().st_size // 1024
    studios = {c["studio"] for c in all_classes}
    print(f"Built {out}  ({size_kb} KB, {len(all_classes)} classes from: {', '.join(sorted(studios))})")


if __name__ == "__main__":
    main()
