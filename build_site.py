#!/usr/bin/env python3
"""
Build index.html — a mobile-optimized dance class schedule site.
Reads *_schedule.json files, normalises the data, and bakes everything
into a single self-contained HTML file.
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
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
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
    if any(x in n for x in ["adv. beg", "adv beg", "beg./adv", "adv/beg"]):
        return "Beginner"
    if any(x in n for x in ["absolute beginner"]):
        return "Beginner"
    if any(x in n for x in ["beginner", " beg ", "beg.", "-beg "]):
        return "Beginner"
    if any(x in n for x in ["all levels", "open level", "all-level"]):
        return "All Levels"
    if any(x in n for x in ["int./adv", "int/adv"]):
        return "Int/Adv"
    if any(x in n for x in ["intermediate", " int ", "int.", "inter "]):
        return "Intermediate"
    if any(x in n for x in ["advanced", " adv ", "adv."]):
        return "Advanced"
    return "All Levels"

def extract_genre(name: str):
    """Returns (genre, subgenre) tuple based on class name."""
    n = name.lower()

    # Ballet family — check early (before 'barre' anywhere)
    if any(x in n for x in ['ballet', 'pointe', 'floor-barre', 'floor barre', 'rommett']):
        if 'pointe' in n: return ('ballet', 'pointe')
        if 'barre'  in n: return ('ballet', 'barre')
        return ('ballet', 'classical')

    # Vogue / ballroom culture
    if any(x in n for x in ['vogue', 'new way', 'old way']):
        return ('street', 'vogue')

    # Waacking / Disco
    if any(x in n for x in ['waack', 'whack', 'disco']):
        return ('street', 'waacking')

    # House
    if 'house' in n:
        return ('street', 'house')

    # Breaking
    if any(x in n for x in ['breaking', 'bboy', 'bgirl', 'breakdanc']):
        return ('street', 'breaking')

    # Popping
    if 'popping' in n:
        return ('street', 'popping')

    # Locking
    if 'locking' in n:
        return ('street', 'locking')

    # Krump
    if 'krump' in n:
        return ('street', 'krump')

    # Litefeet / Tutting / Waving
    if any(x in n for x in ['litefeet', 'tutting', 'waving', 'lite feet']):
        return ('street', 'litefeet')

    # Afrobeats / Afro Fusion
    if any(x in n for x in ['afro', 'african', 'amapiano']):
        return ('afro', 'afrobeats')

    # Contemporary / Modern / Floorwork
    if any(x in n for x in ['contemporary', 'contemp']):
        return ('contemporary', 'contemporary')
    if 'modern' in n:
        return ('contemporary', 'modern')
    if 'lyrical' in n:
        return ('contemporary', 'lyrical')
    if 'floorwork' in n:
        return ('contemporary', 'floorwork')

    # Jazz Funk / Street Jazz → street
    if any(x in n for x in ['jazz funk', 'street jazz', 'jazzfunk']):
        return ('street', 'jazzfunk')

    # Kpop
    if 'kpop' in n or 'k-pop' in n:
        return ('street', 'kpop')

    # Latin
    if any(x in n for x in ['salsa', 'mambo', 'bachata', 'latin', 'tango', 'cumbia', 'reggaeton']):
        return ('latin', 'latin')

    # Heels / Femme (not "Vogue Femme" — already caught above)
    if any(x in n for x in ['heel', 'femme', 'stiletto']):
        return ('heels', 'heels')

    # Hip-Hop (broad — after all specific sub-styles)
    if any(x in n for x in ['hip hop', 'hip-hop', 'hiphop']):
        return ('street', 'hiphop')

    # Street Styles generic
    if any(x in n for x in ['street style', 'urban', 'club style', 'funk style']):
        return ('street', 'street')

    # Jazz generic (after jazz funk)
    if 'jazz' in n:
        return ('contemporary', 'jazz')

    # Yoga / Conditioning
    if any(x in n for x in ['yoga', 'condition', 'pilates', 'stretch']):
        return ('conditioning', 'conditioning')

    return ('other', 'other')

def start_hour(dt) -> float:
    if not dt:
        return -1
    return dt.hour + dt.minute / 60

def normalize_name(name: str) -> str:
    name = re.sub(r"(?i)^(Mover'?s?\s+(Bodega|Modega)\s*[-–:]\s*)", "", name).strip()
    name = re.sub(r"(?i)^(Modega\s*[-–:]\s*)", "", name).strip()
    return name

def get_update_label() -> str:
    """Human-readable timestamp of the most-recent scraper run."""
    candidates = []
    for fname in ["brickhouse_schedule.json", "modega_schedule.json",
                  "peridance_schedule.json", "pjm_schedule.json"]:
        p = HERE / fname
        if p.exists():
            try:
                ts = json.loads(p.read_text()).get("scraped_at", "")
                if ts:
                    candidates.append(parse_dt(ts))
            except Exception:
                pass
    if not candidates:
        return "Updated today"
    latest = max(c for c in candidates if c)
    now_et = datetime.now(ET)
    if latest.date() == now_et.date():
        return f"Updated today at {latest.strftime('%-I:%M %p')}"
    delta = (now_et.date() - latest.date()).days
    if delta == 1:
        return "Updated yesterday"
    if delta < 7:
        return f"Updated {delta} days ago"
    return f"Updated {latest.strftime('%b %-d')}"


# ── load + normalise ──────────────────────────────────────────────────────────

def _make_class(studio, studio_key, class_name, category, instructor,
                start_dt, end_dt, is_canceled, booking_url,
                max_capacity=None, total_booked=None, description="",
                date_str="", level_override=None):
    genre, subgenre = extract_genre(class_name + " " + category)
    start_dt_parsed = start_dt
    end_dt_parsed   = end_dt
    return {
        "studio":        studio,
        "studio_key":    studio_key,
        "class_name":    class_name,
        "category":      category,
        "instructor":    instructor,
        "date_key":      fmt_date_key(start_dt_parsed, date_str),
        "start_dt":      start_dt_parsed,
        "start_display": fmt_time(start_dt_parsed),
        "end_display":   fmt_time(end_dt_parsed),
        "duration_min":  int((end_dt_parsed - start_dt_parsed).total_seconds() / 60)
                         if (start_dt_parsed and end_dt_parsed) else None,
        "level":         level_override or extract_level(class_name + " " + category),
        "genre":         genre,
        "subgenre":      subgenre,
        "start_hour":    start_hour(start_dt_parsed),
        "is_canceled":   is_canceled,
        "booking_url":   booking_url,
        "max_capacity":  max_capacity,
        "total_booked":  total_booked,
        "description":   description,
    }

def load_brickhouse():
    raw = json.loads((HERE / "brickhouse_schedule.json").read_text())
    out = []
    for c in raw["classes"]:
        start_dt = parse_dt(c.get("start_time", ""))
        end_dt   = parse_dt(c.get("end_time", ""))
        name = c.get("class_name", "")
        parts = re.split(r"\s*[-–]\s*", name, maxsplit=1)
        display_name = parts[-1].strip() if len(parts) > 1 else name.strip()
        category     = parts[0].strip()  if len(parts) > 1 else ""
        out.append(_make_class(
            studio="Brickhouse NYC", studio_key="brickhouse",
            class_name=display_name, category=category,
            instructor=c.get("instructor", ""),
            start_dt=start_dt, end_dt=end_dt,
            is_canceled=c.get("is_canceled", False),
            booking_url=c.get("source_url", "https://brickhousedance.com/open-classes/"),
            date_str=c.get("date", ""),
        ))
    return out

def load_modega():
    raw = json.loads((HERE / "modega_schedule.json").read_text())
    out = []
    for c in raw["classes"]:
        start_dt = parse_dt(c.get("start_time", ""))
        end_dt   = parse_dt(c.get("end_time", ""))
        name = normalize_name(c.get("class_name", ""))
        out.append(_make_class(
            studio="Modega", studio_key="modega",
            class_name=name, category="",
            instructor=c.get("instructor", ""),
            start_dt=start_dt, end_dt=end_dt,
            is_canceled=c.get("is_canceled", False),
            booking_url=c.get("booking_url", c.get("source_url", "")),
            max_capacity=c.get("max_capacity"),
            total_booked=c.get("total_booked"),
            description=c.get("description", ""),
            date_str=c.get("date", ""),
        ))
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
        out.append(_make_class(
            studio="Peridance", studio_key="peridance",
            class_name=name, category=c.get("category", ""),
            instructor=c.get("instructor", ""),
            start_dt=start_dt, end_dt=end_dt,
            is_canceled=c.get("is_canceled", False),
            booking_url=c.get("booking_url", "https://peridance.org"),
            date_str=c.get("date", ""),
        ))
    return out

def load_pjm():
    p = HERE / "pjm_schedule.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    out = []
    for c in raw.get("classes", []):
        start_dt = parse_dt(c.get("start_time", ""))
        end_dt   = parse_dt(c.get("end_time", ""))
        name = c.get("class_name", "")
        out.append(_make_class(
            studio="PJM Dance", studio_key="pjm",
            class_name=name, category="",
            instructor=c.get("instructor", ""),
            start_dt=start_dt, end_dt=end_dt,
            is_canceled=c.get("is_canceled", False),
            booking_url=c.get("booking_url",
                "https://go.mindbodyonline.com/book/widgets/schedules/view/e141370d439/schedule"),
            level_override=c.get("level"),
            date_str=c.get("date", ""),
        ))
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
body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:#ddb5c8;overscroll-behavior-y:none;display:flex;justify-content:center}
button{cursor:pointer;font-family:inherit;border:none;background:none;color:inherit}
a{color:inherit;text-decoration:none}

.app-shell{width:100%;max-width:390px;height:100dvh;height:100svh;background:#eceae6;position:relative;display:flex;flex-direction:column;overflow:hidden}
@media(max-width:430px){.app-shell{max-width:100%}}

.bg-radial{position:absolute;inset:0;pointer-events:none;z-index:0;background:linear-gradient(to bottom,#ddb5c8 0%,rgba(221,181,200,0) 18%),radial-gradient(ellipse 75% 50% at 85% 10%,rgba(208,120,155,.65) 0%,transparent 100%)}
.bg-dots{position:absolute;inset:0;pointer-events:none;z-index:0;opacity:.32;background-image:radial-gradient(circle,rgba(0,0,0,.28) 1px,transparent 1px);background-size:2.5px 2.5px}

/* header */
.cal-header{flex-shrink:0;padding:calc(env(safe-area-inset-top) + 20px) 18px 0;position:relative;z-index:10;user-select:none}
.cal-header-inner{position:relative;z-index:1}
.header-row1{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.location-label{font-size:12px;font-weight:500;letter-spacing:.07em;color:#1a1a18;text-transform:uppercase}
.header-actions{display:flex;align-items:center;gap:6px}
.icon-btn{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.45);border:.5px solid rgba(26,26,24,.10);transition:background .15s;-webkit-tap-highlight-color:transparent}
.icon-btn:active{background:rgba(255,255,255,.75)}
.icon-btn svg{width:15px;height:15px;stroke:#1a1a18;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.header-row2{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:16px}
.page-title{font-family:'Permanent Marker',cursive;font-size:28px;font-weight:400;color:#111;line-height:1.1;letter-spacing:.5px}
.updated-text{font-family:'DM Mono',monospace;font-size:10px;color:#8c8a82;font-weight:400;letter-spacing:.02em}

/* week strip */
.week-strip{flex:1;display:flex;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding:6px 0 14px;gap:2px}
.week-strip::-webkit-scrollbar{display:none}
.day-col{flex:1;min-width:42px;display:flex;flex-direction:column;align-items:center;gap:3px;padding:6px 4px;border-radius:8px;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:background .18s}
.day-col.selected{background:#1a1a18}
.day-letter{font-size:10px;font-weight:500;color:#6e6c66;text-transform:uppercase;letter-spacing:.04em}
.day-col.selected .day-letter{color:rgba(236,234,230,.65)}
.day-num{font-family:'DM Mono',monospace;font-size:13px;font-weight:500;color:#1a1a18}
.day-col.selected .day-num{color:#eceae6}
.day-col.today:not(.selected) .day-num{color:#d4537e}
.day-dot{width:4px;height:4px;border-radius:50%;background:#d4537e;opacity:0;transition:opacity .2s;margin-top:1px}
.day-col.has-classes .day-dot{opacity:1}
.day-col.selected .day-dot{background:rgba(236,234,230,.55)}

/* main scroll */
.main-scroll{flex:1;min-height:0;overflow-y:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;padding:8px 16px calc(72px + env(safe-area-inset-bottom));position:relative;z-index:1}
.main-scroll::-webkit-scrollbar{display:none}

.section-divider{display:flex;align-items:center;gap:8px;font-size:11px;font-weight:500;letter-spacing:.05em;color:#9a9688;text-transform:uppercase;margin:8px 0 8px}
.section-divider:first-child{margin-top:2px}
.section-line{flex:1;height:.5px;background:rgba(26,26,24,.16)}
.section-divider.date-divider{text-transform:none;font-size:12px;letter-spacing:.02em;color:#7a7870}

.empty-state{text-align:center;padding:52px 20px}
.empty-icon{font-size:44px;margin-bottom:14px}
.empty-title{font-size:17px;font-weight:600;color:#1a1a18;margin-bottom:6px}
.empty-sub{font-size:13px;color:#9a9688;line-height:1.55}

/* cards */
.card{border-radius:14px;overflow:hidden;margin-bottom:10px;position:relative;transition:transform .15s;animation:slideUp .22s ease both}
.card:active{transform:scale(.985)}
@keyframes slideUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── Genre card palettes ── */
/* Street — purple/violet family; sub-genre varies stripe angle */
.card-street-0{background:linear-gradient(155deg,#1e1240 0%,#0a0622 72%);background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#1e1240 0%,#0a0622 72%)}
.card-street-1{background:linear-gradient(155deg,#22163e 0%,#0e0824 72%);background-image:repeating-linear-gradient(120deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#22163e 0%,#0e0824 72%)}
.card-street-2{background:linear-gradient(155deg,#28103c 0%,#10061e 72%);background-image:repeating-linear-gradient(20deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 6px),linear-gradient(155deg,#28103c 0%,#10061e 72%)}

/* Ballet — green family */
.card-ballet-0{background:linear-gradient(155deg,#0e2818 0%,#040e08 72%);background-image:repeating-linear-gradient(55deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#0e2818 0%,#040e08 72%)}
.card-ballet-1{background:linear-gradient(155deg,#143020 0%,#060e08 72%);background-image:repeating-linear-gradient(130deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#143020 0%,#060e08 72%)}
.card-ballet-2{background:linear-gradient(155deg,#162c12 0%,#081200 72%);background-image:repeating-linear-gradient(25deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#162c12 0%,#081200 72%)}

/* Contemporary — blue family */
.card-contemp-0{background:linear-gradient(155deg,#102038 0%,#060c18 72%);background-image:repeating-linear-gradient(60deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#102038 0%,#060c18 72%)}
.card-contemp-1{background:linear-gradient(155deg,#0e1c3a 0%,#060a1e 72%);background-image:repeating-linear-gradient(140deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#0e1c3a 0%,#060a1e 72%)}
.card-contemp-2{background:linear-gradient(155deg,#0c2034 0%,#041016 72%);background-image:repeating-linear-gradient(30deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#0c2034 0%,#041016 72%)}

/* Afro — amber/gold family */
.card-afro-0{background:linear-gradient(155deg,#2e1a06 0%,#160800 72%);background-image:repeating-linear-gradient(50deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#2e1a06 0%,#160800 72%)}
.card-afro-1{background:linear-gradient(155deg,#321c08 0%,#180a00 72%);background-image:repeating-linear-gradient(115deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#321c08 0%,#180a00 72%)}
.card-afro-2{background:linear-gradient(155deg,#281808 0%,#120600 72%);background-image:repeating-linear-gradient(22deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#281808 0%,#120600 72%)}

/* Latin — crimson family */
.card-latin-0{background:linear-gradient(155deg,#2e0e0e 0%,#160202 72%);background-image:repeating-linear-gradient(70deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#2e0e0e 0%,#160202 72%)}
.card-latin-1{background:linear-gradient(155deg,#300c12 0%,#160408 72%);background-image:repeating-linear-gradient(145deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#300c12 0%,#160408 72%)}
.card-latin-2{background:linear-gradient(155deg,#280c10 0%,#120408 72%);background-image:repeating-linear-gradient(28deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#280c10 0%,#120408 72%)}

/* Heels — rose/magenta family */
.card-heels-0{background:linear-gradient(155deg,#30101e 0%,#160608 72%);background-image:repeating-linear-gradient(65deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#30101e 0%,#160608 72%)}
.card-heels-1{background:linear-gradient(155deg,#2c0e24 0%,#140610 72%);background-image:repeating-linear-gradient(130deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#2c0e24 0%,#140610 72%)}
.card-heels-2{background:linear-gradient(155deg,#34141e 0%,#180808 72%);background-image:repeating-linear-gradient(15deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#34141e 0%,#180808 72%)}

/* Other / Conditioning / Tap — warm neutral */
.card-other-0{background:linear-gradient(155deg,#201c14 0%,#0e0c06 72%);background-image:repeating-linear-gradient(80deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#201c14 0%,#0e0c06 72%)}
.card-other-1{background:linear-gradient(155deg,#1e1a14 0%,#0c0a08 72%);background-image:repeating-linear-gradient(155deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#1e1a14 0%,#0c0a08 72%)}
.card-other-2{background:linear-gradient(155deg,#221c10 0%,#100c04 72%);background-image:repeating-linear-gradient(35deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#221c10 0%,#100c04 72%)}

.card-canceled{opacity:.48}
.card-inner{padding:14px;position:relative;z-index:1}
.card-top-row{display:flex;justify-content:flex-end;margin-bottom:4px}
.save-btn{color:rgba(232,228,220,.4);line-height:1;padding:2px;transition:color .2s;position:relative;z-index:3}
.save-btn svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;transition:fill .2s,stroke .2s}
.save-btn.saved{color:#d4537e}
.save-btn.saved svg{fill:#d4537e;stroke:#d4537e}

/* studio + time label (replaced level pill) */
.card-meta{font-family:'DM Mono',monospace;font-size:10px;color:rgba(216,212,204,.65);letter-spacing:.04em;margin-bottom:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-name{font-family:'DM Sans',sans-serif;color:#fff;font-size:19px;font-weight:500;line-height:1.2;margin-bottom:10px}
.card-instructor-row{display:flex;align-items:center;gap:6px}
.small-avatar{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:9px;color:#fff;font-weight:500}
.card-instructor-name{color:#b5b1a6;font-size:12px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.cap-wrap{margin-top:10px}
.cap-bar-bg{height:2px;background:rgba(255,255,255,.12);border-radius:1px}
.cap-bar-fill{height:2px;border-radius:1px;background:rgba(255,255,255,.42)}
.cap-text{font-family:'DM Mono',monospace;font-size:10px;color:rgba(232,228,220,.48);margin-top:4px;letter-spacing:.02em}
.card-tap{position:absolute;inset:0;z-index:2}

/* bottom nav */
.bottom-nav{position:absolute;bottom:0;left:0;right:0;display:flex;justify-content:space-around;padding:10px 0 calc(14px + env(safe-area-inset-bottom));background:rgba(236,234,230,.95);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-top:.5px solid rgba(26,26,24,.10);z-index:50}
.nav-item{display:flex;flex-direction:column;align-items:center;gap:3px;cursor:pointer;-webkit-tap-highlight-color:transparent;padding:0 18px}
.nav-icon svg{width:22px;height:22px;stroke:#9a9688;fill:none;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;transition:stroke .15s}
.nav-label{font-size:10px;color:#9a9688;font-weight:500;transition:color .15s}
.nav-item.active .nav-icon svg{stroke:#1a1a18}
.nav-item.active .nav-label{color:#1a1a18;font-weight:600}

/* drawer */
.drawer-overlay{position:fixed;inset:0;z-index:200;background:rgba(26,26,24,0);pointer-events:none;transition:background .3s}
.drawer-overlay.open{background:rgba(26,26,24,.5);pointer-events:all}
.drawer{position:fixed;bottom:0;left:50%;transform:translateX(-50%) translateY(100%);width:100%;max-width:390px;z-index:201;background:#fff;border-radius:24px 24px 0 0;padding:0 0 calc(20px + env(safe-area-inset-bottom));transition:transform .35s cubic-bezier(.32,1,.36,1);max-height:92svh;display:flex;flex-direction:column}
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

/* genre dot indicators on filter chips */
.fchip .gdot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;opacity:.85}

.teacher-search-wrap{margin-bottom:12px}
.teacher-search{width:100%;padding:10px 14px;border-radius:12px;border:1.5px solid #e8e4de;font-size:14px;color:#1a1a18;outline:none;font-family:inherit;background:#faf9f7;-webkit-appearance:none}
.teacher-search:focus{border-color:#1a1a18}
.teacher-chip-row{display:flex;flex-wrap:wrap;gap:6px;align-items:flex-start}
.fav-teacher-label{font-size:10px;font-weight:600;color:#9a9688;text-transform:uppercase;letter-spacing:.07em;margin:8px 0 6px;width:100%}
.tchip-wrap{display:inline-flex;align-items:center;gap:0}
.tchip{padding:7px 11px;border-radius:18px 0 0 18px;font-size:12px;font-weight:500;color:#3a3830;background:#f0ece6;border:1.5px solid transparent;border-right:none;transition:all .15s}
.tchip.active{background:#1a1a18;color:#eceae6}
.tchip-all{border-radius:18px;border-right:1.5px solid transparent}
.heart-btn{padding:7px 9px 7px 7px;border-radius:0 18px 18px 0;background:#f0ece6;font-size:13px;line-height:1;color:#ccc;transition:color .2s;border:1.5px solid transparent;border-left:none}
.heart-btn.hearted{color:#d4537e}

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
  <div class="bg-radial"></div>
  <div class="bg-dots"></div>

  <header class="cal-header">
    <div class="cal-header-inner">
      <div class="header-row1">
        <span class="location-label">New York City</span>
        <div class="header-actions">
          <button class="icon-btn" id="filterBtn" title="Filters">
            <svg viewBox="0 0 16 16"><path d="M2 4h12M5 8h6M7 12h2"/></svg>
          </button>
        </div>
      </div>
      <div class="header-row2">
        <h1 class="page-title" id="pageTitle">July</h1>
        <span class="updated-text" id="updatedText">__UPDATED_LABEL__</span>
      </div>
      <div class="week-strip" id="weekStrip"></div>
    </div>
  </header>

  <main class="main-scroll" id="mainScroll">
    <div id="classesList"></div>
  </main>

  <nav class="bottom-nav">
    <div class="nav-item active" id="scheduleNav">
      <div class="nav-icon"><svg viewBox="0 0 22 22"><rect x="3" y="4" width="16" height="15" rx="2"/><path d="M7 2v4M15 2v4M3 9h16"/></svg></div>
      <span class="nav-label">Schedule</span>
    </div>
    <div class="nav-item" id="popupNav">
      <div class="nav-icon"><svg viewBox="0 0 22 22"><path d="M11 3v18M3 8l8-5 8 5"/><rect x="5" y="11" width="12" height="10" rx="1"/></svg></div>
      <span class="nav-label">Pop up</span>
    </div>
    <div class="nav-item" id="savedNav">
      <div class="nav-icon"><svg viewBox="0 0 22 22"><path d="M5 3h12a1 1 0 0 1 1 1v15l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg></div>
      <span class="nav-label">Saved</span>
    </div>
  </nav>
</div>

<div class="drawer-overlay" id="drawerOverlay"></div>

<div class="drawer" id="drawer">
  <div class="drawer-handle"></div>
  <div class="drawer-header">
    <span class="drawer-title">Filters</span>
    <button class="drawer-close" id="drawerClose">✕</button>
  </div>
  <div class="drawer-scroll">

    <div class="fsection">
      <div class="fsection-label">Studio</div>
      <div class="fchip-row" id="studioChipRow">
        <button class="fchip active" data-studio="all">All</button>
        <button class="fchip" data-studio="brickhouse">Brickhouse NYC</button>
        <button class="fchip" data-studio="modega">Modega</button>
        <button class="fchip" data-studio="peridance">Peridance</button>
        <button class="fchip" data-studio="pjm">PJM Dance</button>
      </div>
    </div>

    <div class="fsection">
      <div class="fsection-label">Genre</div>
      <div class="fchip-row" id="genreChipRow">
        <button class="fchip active" data-genre="all">All</button>
        <button class="fchip" data-genre="street"><span class="gdot" style="background:#6b3fa0"></span>Street</button>
        <button class="fchip" data-genre="ballet"><span class="gdot" style="background:#1a6e38"></span>Ballet</button>
        <button class="fchip" data-genre="contemporary"><span class="gdot" style="background:#1a3a7a"></span>Contemporary</button>
        <button class="fchip" data-genre="afro"><span class="gdot" style="background:#b87c1a"></span>Afrobeats</button>
        <button class="fchip" data-genre="latin"><span class="gdot" style="background:#9a1a1a"></span>Latin</button>
        <button class="fchip" data-genre="heels"><span class="gdot" style="background:#9a1a4a"></span>Heels</button>
        <button class="fchip" data-genre="other"><span class="gdot" style="background:#5a5040"></span>Other</button>
      </div>
    </div>

    <div class="fsection">
      <div class="fsection-label">Level</div>
      <div class="fchip-row" id="levelChipRow">
        <button class="fchip active" data-level="all">All</button>
        <button class="fchip" data-level="Beginner">Beginner</button>
        <button class="fchip" data-level="All Levels">Open</button>
        <button class="fchip" data-level="Intermediate">Intermediate</button>
        <button class="fchip" data-level="Int/Adv">Int/Adv</button>
        <button class="fchip" data-level="Advanced">Advanced</button>
      </div>
    </div>

    <div class="fsection">
      <div class="fsection-label">Time of Day</div>
      <div class="time-display-row">
        <span id="timeStartLabel">12:00 PM</span>
        <span id="timeEndLabel">12:00 AM</span>
      </div>
      <div class="range-slider-wrap">
        <div class="slider-track-bg"></div>
        <div class="slider-track-fill" id="sliderFill"></div>
        <input type="range" id="rangeMin" min="6" max="24" step="0.5" value="12"/>
        <input type="range" id="rangeMax" min="6" max="24" step="0.5" value="24"/>
      </div>
    </div>

    <div class="fsection">
      <div class="fsection-label">Teacher</div>
      <div class="teacher-search-wrap">
        <input type="search" id="teacherSearch" class="teacher-search" placeholder="Search teachers…" autocomplete="off" autocorrect="off" spellcheck="false"/>
      </div>
      <div class="teacher-chip-row" id="teacherChipRow"></div>
    </div>

  </div>
  <div class="drawer-footer">
    <button class="apply-btn" id="applyBtn">Show classes</button>
  </div>
</div>

<script>
const ALL_CLASSES = __ALL_CLASSES__;

// ── bookmarks ──
function classId(c){return c.date_key+'|'+c.studio_key+'|'+c.class_name+'|'+c.start_display}
let savedSet=new Set(JSON.parse(localStorage.getItem('nyd_saved')||'[]'));
function isSaved(c){return savedSet.has(classId(c))}
function toggleSaved(c){
  const id=classId(c);let now;
  if(savedSet.has(id)){savedSet.delete(id);now=false}else{savedSet.add(id);now=true}
  localStorage.setItem('nyd_saved',JSON.stringify([...savedSet]));
  return now;
}

// ── fav teachers ──
let favTeachers=new Set(JSON.parse(localStorage.getItem('nyd_fav_t')||'[]'));
function toggleFavTeacher(name){
  if(favTeachers.has(name))favTeachers.delete(name);else favTeachers.add(name);
  localStorage.setItem('nyd_fav_t',JSON.stringify([...favTeachers]));
}

// ── state ──
// studios: Set — 'all' means no filter, otherwise contains studio_key values
const S={weekOffset:0,selectedDate:'',studios:new Set(['all']),genre:'all',level:'all',teacher:'all',timeMin:12,timeMax:24,tab:'schedule'};

// ── genre → card style ──
const GENRE_STYLES={
  street:      ['card-street-0','card-street-1','card-street-2'],
  ballet:      ['card-ballet-0','card-ballet-1','card-ballet-2'],
  contemporary:['card-contemp-0','card-contemp-1','card-contemp-2'],
  afro:        ['card-afro-0','card-afro-1','card-afro-2'],
  latin:       ['card-latin-0','card-latin-1','card-latin-2'],
  heels:       ['card-heels-0','card-heels-1','card-heels-2'],
  conditioning:['card-other-0','card-other-1','card-other-2'],
  tap:         ['card-other-0','card-other-1','card-other-2'],
  other:       ['card-other-0','card-other-1','card-other-2'],
};
function cardStyle(c){
  const styles=GENRE_STYLES[c.genre]||GENRE_STYLES.other;
  let h=0;for(const ch of(c.subgenre||''))h=(h*31+ch.charCodeAt(0))>>>0;
  return styles[h%3];
}

const AV_COLORS=['#639922','#534ab7','#1d9e75','#d4537e','#ba7517','#2a6cb5','#9e4a20','#7b5ea7','#c05a3c','#1f8e8e'];
function avatarColor(name){if(!name)return'#888';let h=0;for(const c of name)h=(h*31+c.charCodeAt(0))>>>0;return AV_COLORS[h%AV_COLORS.length]}
function initials(name){if(!name)return'?';const p=name.trim().split(/\s+/);return p.length===1?p[0].slice(0,2).toUpperCase():(p[0][0]+p[p.length-1][0]).toUpperCase()}
function fmtHour(h){if(h>=24)return'12:00 AM';const hr=Math.floor(h),mn=Math.round((h-hr)*60),period=hr>=12?'PM':'AM',dh=hr>12?hr-12:(hr===0?12:hr);return`${dh}:${mn.toString().padStart(2,'0')} ${period}`}
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

const DAY_LETTERS=['SUN','MON','TUE','WED','THU','FRI','SAT'];
const DAY_NAMES=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
const MONTHS_SHORT=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function todayKey(){const d=new Date();return isoKey(d)}
function isoKey(d){return`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
function weekStartDate(off){const d=new Date();d.setHours(0,0,0,0);d.setDate(d.getDate()-d.getDay()+off*7);return d}
function addDays(d,n){const r=new Date(d);r.setDate(r.getDate()+n);return r}
function formatDateFull(dateKey){
  const[y,m,d]=dateKey.split('-').map(Number);const dt=new Date(y,m-1,d);
  return`${DAY_NAMES[dt.getDay()]}, ${MONTHS_SHORT[dt.getMonth()]} ${d}`;
}

function matchesFilters(c){
  if(!S.studios.has('all')&&!S.studios.has(c.studio_key))return false;
  if(S.genre!=='all'&&c.genre!==S.genre)return false;
  if(S.level!=='all'&&c.level!==S.level)return false;
  if(S.teacher!=='all'&&c.instructor!==S.teacher)return false;
  const h=c.start_hour;if(h>=0&&(h<S.timeMin||h>S.timeMax))return false;
  return true;
}
function filteredForDate(dateKey){
  return ALL_CLASSES.filter(c=>c.date_key===dateKey&&!c.is_canceled&&matchesFilters(c));
}
function datesWithClasses(){
  const s=new Set();
  ALL_CLASSES.forEach(c=>{if(!c.is_canceled&&matchesFilters(c))s.add(c.date_key)});
  return s;
}

// ── calendar ──
function renderCalendar(){
  const strip=document.getElementById('weekStrip');
  const start=weekStartDate(S.weekOffset);
  const dotDates=datesWithClasses();
  const today=todayKey();
  const mid=addDays(start,3);
  document.getElementById('pageTitle').textContent=MONTHS[mid.getMonth()]+' \''+String(mid.getFullYear()).slice(-2);
  strip.innerHTML='';
  for(let i=0;i<7;i++){
    const d=addDays(start,i);const key=isoKey(d);
    const col=document.createElement('div');
    col.className='day-col'+(key===S.selectedDate?' selected':'')+(key===today?' today':'')+(dotDates.has(key)?' has-classes':'');
    col.innerHTML=`<span class="day-letter">${DAY_LETTERS[d.getDay()]}</span><span class="day-num">${d.getDate()}</span><span class="day-dot"></span>`;
    col.addEventListener('click',()=>{S.selectedDate=key;renderAll()});
    strip.appendChild(col);
  }
}

// ── classes ──
function renderClasses(){
  const listEl=document.getElementById('classesList');
  if(!S.selectedDate){listEl.innerHTML='';return}
  const classes=filteredForDate(S.selectedDate);
  if(!classes.length){
    listEl.innerHTML=`<div class="empty-state"><div class="empty-icon">🕺</div><div class="empty-title">No classes this day</div><div class="empty-sub">Try different filters or pick another day.</div></div>`;
    return;
  }
  classes.sort((a,b)=>a.start_hour-b.start_hour);
  listEl.innerHTML='';let lastSec='';
  classes.forEach((c,i)=>{
    const sec=c.start_hour<12?'Morning':c.start_hour<17?'Afternoon':'Evening';
    if(sec!==lastSec){
      const div=document.createElement('div');div.className='section-divider';
      div.innerHTML=`${sec}<div class="section-line"></div>`;
      listEl.appendChild(div);lastSec=sec;
    }
    listEl.appendChild(buildCard(c,i));
  });
}

// ── saved tab ──
function renderSaved(){
  document.getElementById('pageTitle').textContent='Saved';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  const listEl=document.getElementById('classesList');
  const savedClasses=ALL_CLASSES.filter(c=>isSaved(c));
  if(!savedClasses.length){
    listEl.innerHTML=`<div class="empty-state"><div class="empty-icon">🔖</div><div class="empty-title">No saved classes yet</div><div class="empty-sub">Tap the bookmark on any card to save it here.</div></div>`;
    return;
  }
  savedClasses.sort((a,b)=>a.date_key<b.date_key?-1:a.date_key>b.date_key?1:a.start_hour-b.start_hour);
  listEl.innerHTML='';let lastDate='';
  savedClasses.forEach((c,i)=>{
    if(c.date_key!==lastDate){
      const div=document.createElement('div');div.className='section-divider date-divider';
      div.innerHTML=`${formatDateFull(c.date_key)}<div class="section-line"></div>`;
      listEl.appendChild(div);lastDate=c.date_key;
    }
    listEl.appendChild(buildCard(c,i));
  });
}

// ── card builder ──
function buildCard(c,i){
  const div=document.createElement('div');
  div.className=`card ${cardStyle(c)}${c.is_canceled?' card-canceled':''}`;
  div.style.animationDelay=`${Math.min(i*35,200)}ms`;

  const color=avatarColor(c.instructor);
  const abbr=initials(c.instructor);
  const timeStr=c.start_display?(c.end_display?`${c.start_display} – ${c.end_display}`:c.start_display):'';
  const metaStr=c.studio+(timeStr?' · '+timeStr:'');
  const saved=isSaved(c);

  let capHTML='';
  if(c.max_capacity>0&&c.total_booked!=null){
    const pct=Math.min(100,Math.round(c.total_booked/c.max_capacity*100));
    const spots=c.max_capacity-c.total_booked;
    const capText=spots<=0?'Full':spots<=5?`${spots} spots left`:`${c.total_booked}/${c.max_capacity}`;
    capHTML=`<div class="cap-wrap"><div class="cap-bar-bg"><div class="cap-bar-fill" style="width:${pct}%"></div></div><div class="cap-text">${capText}</div></div>`;
  }
  const bookHref=c.booking_url&&!c.is_canceled?`<a href="${esc(c.booking_url)}" target="_blank" rel="noopener" class="card-tap" aria-label="Book ${esc(c.class_name)}"></a>`:'';

  div.innerHTML=`${bookHref}
    <div class="card-inner">
      <div class="card-top-row">
        <button class="save-btn${saved?' saved':''}" aria-label="${saved?'Unsave':'Save'}">
          <svg viewBox="0 0 16 16"><path d="M3 2h10a1 1 0 0 1 1 1v11l-5-3-5 3V3a1 1 0 0 1 1-1z"/></svg>
        </button>
      </div>
      <div class="card-meta">${esc(metaStr)}</div>
      <div class="card-name">${esc(c.class_name)}</div>
      <div class="card-instructor-row">
        <div class="small-avatar" style="background:${color}">${abbr}</div>
        <span class="card-instructor-name">${esc(c.instructor||'—')}</span>
      </div>
      ${capHTML}
    </div>`;

  div.querySelector('.save-btn').addEventListener('click',e=>{
    e.preventDefault();e.stopPropagation();
    const nowSaved=toggleSaved(c);
    const btn=e.currentTarget;
    btn.classList.toggle('saved',nowSaved);
    btn.setAttribute('aria-label',nowSaved?'Unsave':'Save');
    if(S.tab==='saved')setTimeout(renderSaved,60);
  });
  return div;
}

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

// ── studio chips (multi-select) ──
function initStudioChips(){
  document.querySelectorAll('#studioChipRow .fchip').forEach(chip=>{
    chip.addEventListener('click',()=>{
      const val=chip.dataset.studio;
      if(val==='all'){
        S.studios=new Set(['all']);
        document.querySelectorAll('#studioChipRow .fchip').forEach(c=>{
          c.classList.toggle('active',c.dataset.studio==='all');
        });
      } else {
        S.studios.delete('all');
        chip.classList.toggle('active');
        if(chip.classList.contains('active')) S.studios.add(val);
        else S.studios.delete(val);
        if(S.studios.size===0){S.studios.add('all');}
        document.querySelector('#studioChipRow .fchip[data-studio="all"]')
          .classList.toggle('active',S.studios.has('all'));
      }
      buildTeacherChips();updateApplyBtn();
    });
  });
}

// ── genre chips (single-select) ──
function initGenreChips(){
  document.querySelectorAll('#genreChipRow .fchip').forEach(chip=>{
    chip.addEventListener('click',()=>{
      document.querySelectorAll('#genreChipRow .fchip').forEach(c=>c.classList.remove('active'));
      chip.classList.add('active');
      S.genre=chip.dataset.genre;
      updateApplyBtn();
    });
  });
}

// ── level chips ──
function initLevelChips(){
  document.querySelectorAll('#levelChipRow .fchip').forEach(chip=>{
    chip.addEventListener('click',()=>{
      document.querySelectorAll('#levelChipRow .fchip').forEach(c=>c.classList.remove('active'));
      chip.classList.add('active');
      S.level=chip.dataset.level;
      updateApplyBtn();
    });
  });
}

// ── teacher chips with search + hearts ──
function buildTeacherChips(){
  const searchInput=document.getElementById('teacherSearch');
  const searchVal=(searchInput?searchInput.value:'').toLowerCase().trim();
  const row=document.getElementById('teacherChipRow');

  const teachers=[...new Set(
    ALL_CLASSES
      .filter(c=>S.studios.has('all')||S.studios.has(c.studio_key))
      .filter(c=>c.instructor&&!c.instructor.includes('LLC')&&c.instructor!=='Various *'&&c.instructor!=='Modega')
      .map(c=>c.instructor)
  )].sort();

  const matched=searchVal?teachers.filter(t=>t.toLowerCase().includes(searchVal)):teachers;
  const favs=matched.filter(t=>favTeachers.has(t));
  const rest=matched.filter(t=>!favTeachers.has(t));

  row.innerHTML='';
  const allChip=document.createElement('button');
  allChip.className='tchip tchip-all'+(S.teacher==='all'?' active':'');
  allChip.textContent='All';
  allChip.addEventListener('click',()=>{S.teacher='all';buildTeacherChips();updateApplyBtn()});
  row.appendChild(allChip);

  if(favs.length){
    const hdr=document.createElement('div');hdr.className='fav-teacher-label';hdr.textContent='♥ Favorites';
    row.appendChild(hdr);favs.forEach(t=>row.appendChild(makeTchip(t)));
  }
  if(rest.length){
    if(favs.length){const hdr=document.createElement('div');hdr.className='fav-teacher-label';hdr.textContent='All teachers';row.appendChild(hdr)}
    rest.forEach(t=>row.appendChild(makeTchip(t)));
  }
  if(!matched.length){
    const el=document.createElement('div');el.style.cssText='font-size:13px;color:#9a9688;padding:4px 0';el.textContent='No teachers found';row.appendChild(el);
  }
}
function makeTchip(t){
  const wrap=document.createElement('div');wrap.className='tchip-wrap';
  const chip=document.createElement('button');
  chip.className='tchip'+(S.teacher===t?' active':'');
  chip.textContent=t;
  chip.addEventListener('click',()=>{S.teacher=t;buildTeacherChips();updateApplyBtn()});
  const heart=document.createElement('button');
  heart.className='heart-btn'+(favTeachers.has(t)?' hearted':'');
  heart.textContent=favTeachers.has(t)?'♥':'♡';
  heart.addEventListener('click',e=>{e.stopPropagation();toggleFavTeacher(t);buildTeacherChips();updateApplyBtn()});
  wrap.appendChild(chip);wrap.appendChild(heart);return wrap;
}

// ── slider ──
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

// ── apply button: "Show X classes in next Y days" ──
function updateApplyBtn(){
  const today=todayKey();
  const future=ALL_CLASSES.filter(c=>!c.is_canceled&&c.date_key>=today&&matchesFilters(c));
  const n=future.length;
  const btn=document.getElementById('applyBtn');
  if(!n){btn.textContent='No upcoming classes';return}
  const dates=future.map(c=>c.date_key).sort();
  const lastDate=dates[dates.length-1];
  const[ly,lm,ld]=lastDate.split('-').map(Number);
  const[ty,tm,td]=today.split('-').map(Number);
  const days=Math.round((new Date(ly,lm-1,ld)-new Date(ty,tm-1,td))/86400000)+1;
  btn.textContent=`Show ${n} classes in next ${days} days`;
}

// ── tab switching ──
function switchTab(tab){
  if(tab==='popup'){openDrawer();return}
  S.tab=tab;
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById(tab==='schedule'?'scheduleNav':'savedNav').classList.add('active');
  if(tab==='schedule'){
    document.getElementById('weekStrip').style.display='';
    document.getElementById('updatedText').style.visibility='visible';
    renderAll();
  } else {
    renderSaved();
  }
}

// ── event listeners ──
document.getElementById('rangeMin').addEventListener('input',updateSlider);
document.getElementById('rangeMax').addEventListener('input',updateSlider);
document.getElementById('filterBtn').addEventListener('click',openDrawer);
document.getElementById('drawerClose').addEventListener('click',closeDrawer);
document.getElementById('drawerOverlay').addEventListener('click',closeDrawer);
document.getElementById('applyBtn').addEventListener('click',()=>{closeDrawer();renderAll()});
document.getElementById('teacherSearch').addEventListener('input',buildTeacherChips);
['scheduleNav','popupNav','savedNav'].forEach(id=>{
  document.getElementById(id).addEventListener('click',()=>{
    switchTab(id==='scheduleNav'?'schedule':id==='popupNav'?'popup':'saved');
  });
});

function renderAll(){renderCalendar();renderClasses()}

// ── init ──
(function init(){
  initStudioChips();initGenreChips();initLevelChips();
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
    pjm = load_pjm()
    all_classes = sorted(
        bh + md + per + pjm,
        key=lambda c: (c["date_key"], c["start_hour"] if c["start_hour"] >= 0 else 99)
    )

    js_data = to_js_obj(all_classes)
    update_label = get_update_label()
    html = HTML.replace("__ALL_CLASSES__", js_data)
    html = html.replace("__UPDATED_LABEL__", update_label)

    out = HERE / "index.html"
    out.write_text(html)
    size_kb = out.stat().st_size // 1024

    # genre breakdown for sanity check
    from collections import Counter
    genre_counts = Counter(c["genre"] for c in all_classes if not c["is_canceled"])
    studios = {c["studio"] for c in all_classes}
    print(f"Built {out}  ({size_kb} KB, {len(all_classes)} classes from: {', '.join(sorted(studios))})")
    print("Genre breakdown:", dict(genre_counts.most_common()))


if __name__ == "__main__":
    main()
