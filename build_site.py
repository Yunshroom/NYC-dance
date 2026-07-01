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

    # Choreography / Choreo (after style-specific checks so "Choreo Hip Hop" etc. don't land here)
    if any(x in n for x in ['choreography', 'choreo']):
        return ('choreo', 'choreo')

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
    cat = category or ""
    genre, subgenre = extract_genre(class_name + " " + cat)
    start_dt_parsed = start_dt
    end_dt_parsed   = end_dt
    return {
        "studio":        studio,
        "studio_key":    studio_key,
        "class_name":    class_name,
        "category":      cat,
        "instructor":    instructor,
        "date_key":      fmt_date_key(start_dt_parsed, date_str),
        "start_dt":      start_dt_parsed,
        "start_display": fmt_time(start_dt_parsed),
        "end_display":   fmt_time(end_dt_parsed),
        "duration_min":  int((end_dt_parsed - start_dt_parsed).total_seconds() / 60)
                         if (start_dt_parsed and end_dt_parsed) else None,
        "level":         level_override or extract_level(class_name + " " + cat),
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
    _STUDIO_NAMES = {"Modega", "Mover's Bodega, LLC", "Mover's Bodega"}
    _HOST_RE = re.compile(r'[Hh]osted with\s+(.+?)(?:\s*\.|$)', re.IGNORECASE)
    for c in raw["classes"]:
        start_dt = parse_dt(c.get("start_time", ""))
        end_dt   = parse_dt(c.get("end_time", ""))
        name = normalize_name(c.get("class_name", ""))
        raw_instr = c.get("instructor", "")
        if raw_instr in _STUDIO_NAMES:
            # Try to extract host from description, e.g. "Hosted with Static"
            desc = c.get("description", "")
            m = _HOST_RE.search(desc)
            if m:
                host = m.group(1).strip()
                # "Soul Circle: Leo, Liam" → "Soul Circle"; "NIVDO: Law..." → "NIVDO"
                if ':' in host:
                    host = host.split(':')[0].strip()
                # Strip Instagram handles like "(@name)" or "@name"
                host = re.sub(r'\(@[^)]*\)', '', host).strip()
                host = re.sub(r',?\s*@\S+', '', host).strip()
                host = re.sub(r',\s*and\s+@\S+', '', host).strip()
                # Trim trailing comma/and
                host = re.sub(r',?\s*and\s*$', '', host).strip().rstrip(',').strip()
                # If multiple names separated by commas, keep first two max
                parts = [p.strip() for p in re.split(r',\s*', host) if p.strip()]
                if len(parts) > 2:
                    host = parts[0] + ' & ' + parts[1]
                elif parts:
                    host = ', '.join(parts)
                instructor = host if host and host.upper() != 'TBD' else "Modega Staff"
            else:
                instructor = "Modega Staff"
        else:
            instructor = raw_instr
        out.append(_make_class(
            studio="Modega", studio_key="modega",
            class_name=name, category="",
            instructor=instructor,
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

import base64 as _b64

def _watermark_data_url() -> str:
    """Load watermark PNG and return as base64 data URL for inlining."""
    p = HERE / "watermark_small.png"
    if p.exists():
        return "data:image/png;base64," + _b64.b64encode(p.read_bytes()).decode()
    return ""  # fallback: no watermark image

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
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover"/>
<meta name="theme-color" content="#ddb5c8"/>
<title>NYC Dance</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700&family=Permanent+Marker&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://unpkg.com/@phosphor-icons/web@2.1.1"></script>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;width:100%}
html{-webkit-text-size-adjust:100%;background:#ddb5c8}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:#ddb5c8;overscroll-behavior-y:none;touch-action:manipulation}
button{cursor:pointer;font-family:inherit;border:none;background:none;color:inherit;touch-action:manipulation}
a{color:inherit;text-decoration:none}

.app-shell{width:100%;height:100dvh;height:100svh;background:#eceae6;position:relative;display:flex;flex-direction:column;overflow:hidden}
@media(min-width:500px){body{display:flex;justify-content:center}.app-shell{max-width:430px;}}

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
.icon-btn i{font-size:17px;color:#1a1a18;display:flex}
.header-row2{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:16px}
.page-title{font-family:'Permanent Marker',cursive;font-size:28px;font-weight:400;color:#111;line-height:1.1;letter-spacing:.5px}
.updated-text{font-family:'DM Mono',monospace;font-size:10px;color:#8c8a82;font-weight:400;letter-spacing:.02em}

/* week strip */
.week-strip{flex:1;display:flex;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding:6px 0 14px;gap:2px;touch-action:pan-x}
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

/* Choreo — teal/dark-cyan family */
.card-choreo-0{background:linear-gradient(155deg,#082428 0%,#020c10 72%);background-image:repeating-linear-gradient(75deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#082428 0%,#020c10 72%)}
.card-choreo-1{background:linear-gradient(155deg,#061e24 0%,#020a0e 72%);background-image:repeating-linear-gradient(145deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#061e24 0%,#020a0e 72%)}
.card-choreo-2{background:linear-gradient(155deg,#0a2020 0%,#040e0e 72%);background-image:repeating-linear-gradient(28deg,rgba(255,255,255,.048) 0,rgba(255,255,255,.048) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#0a2020 0%,#040e0e 72%)}

.card-canceled{opacity:.48}
.card-past{opacity:.42}
.card-past .card-tap{pointer-events:none}
/* card-inner has no z-index so save-btn can rise above card-tap in card's stacking context */
.card-inner{padding:14px;position:relative}
.card-tap{position:absolute;inset:0;z-index:1}
.card-header-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:7px}
.card-actions{display:flex;align-items:center;gap:0;position:relative;z-index:2;flex-shrink:0}
.save-btn,.my-btn{color:rgba(232,228,220,.4);line-height:1;padding:2px 3px;transition:color .2s;background:none;border:none;cursor:pointer;-webkit-tap-highlight-color:transparent}
.save-btn{padding-left:6px}
.save-btn i,.my-btn i{font-size:19px;transition:color .2s}
.save-btn.saved{color:#d4537e}
.save-btn.saved i{color:#d4537e}
.my-btn.stamped{color:#f0a830}
.my-btn.stamped i{color:#f0a830}
/* Scrapbook notes */
.sticky-note{border-radius:4px;padding:11px 13px;position:relative;border-bottom:2px solid rgba(0,0,0,.07);transition:transform .2s}
.sticky-tape{position:absolute;top:-7px;left:50%;transform:translateX(-50%);width:30px;height:11px;border-radius:2px;opacity:.5}
@keyframes noteIn{from{opacity:0;transform:scale(.88) rotate(var(--r,0deg))}to{opacity:1;transform:scale(1) rotate(var(--r,0deg))}}
.note-in{animation:noteIn .32s cubic-bezier(.34,1.4,.5,1) both}
@keyframes recPulse{0%,100%{opacity:1}50%{opacity:.4}}
.rec-pulse{animation:recPulse 1.2s ease-in-out infinite}
.note-pill-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;border:none;border-radius:999px;padding:9px 14px;cursor:pointer;font-family:'DM Mono',monospace;font-size:11px;-webkit-tap-highlight-color:transparent;transition:opacity .15s}

/* studio + time — now lives in card-header-row beside bookmark */
.card-meta{font-family:'DM Mono',monospace;font-size:10px;color:rgba(216,212,204,.65);letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.card-name{font-family:'DM Sans',sans-serif;color:#fff;font-size:19px;font-weight:500;line-height:1.2;margin-bottom:10px}
.card-instructor-row{display:flex;align-items:center;gap:6px}
.small-avatar{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:9px;color:#fff;font-weight:500}
.card-instructor-name{color:#b5b1a6;font-size:12px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.cap-wrap{margin-top:10px}
.cap-bar-bg{height:2px;background:rgba(255,255,255,.12);border-radius:1px}
.cap-bar-fill{height:2px;border-radius:1px;background:rgba(255,255,255,.42)}
.cap-text{font-family:'DM Mono',monospace;font-size:10px;color:rgba(232,228,220,.48);margin-top:4px;letter-spacing:.02em}

/* ── glassmorphic pill nav ── */
#bottomNav{position:absolute;bottom:0;left:0;right:0;display:flex;justify-content:center;padding:12px 20px calc(12px + env(safe-area-inset-bottom));z-index:50;pointer-events:none}
.nav-bar{position:relative;display:inline-flex;align-items:center;gap:2px;background:rgba(14,12,10,.48);backdrop-filter:blur(28px) saturate(1.8);-webkit-backdrop-filter:blur(28px) saturate(1.8);border:.5px solid rgba(255,255,255,.13);border-radius:50px;padding:5px;box-shadow:0 8px 32px rgba(0,0,0,.28),0 1px 0 rgba(255,255,255,.07) inset;pointer-events:all}
.nav-capsule{position:absolute;border-radius:40px;background:rgba(50,44,38,.52);border:.5px solid rgba(255,255,255,.2);box-shadow:0 2px 10px rgba(0,0,0,.3),0 .5px 0 rgba(255,255,255,.07) inset;top:5px;bottom:5px;left:5px;pointer-events:none;transition:left .38s cubic-bezier(.34,1.4,.64,1),width .38s cubic-bezier(.34,1.4,.64,1)}
.nav-tab{position:relative;z-index:1;display:flex;align-items:center;gap:0;padding:9px 12px;border-radius:40px;background:none;border:none;cursor:pointer;-webkit-tap-highlight-color:transparent}
.tab-icon i{font-size:21px;color:rgba(140,132,120,.85);display:block;flex-shrink:0;transition:color .2s}
.tab-label{font-size:13px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;max-width:0;opacity:0;margin-left:0;transition:max-width .38s cubic-bezier(.34,1.4,.64,1),margin-left .38s cubic-bezier(.34,1.4,.64,1)}
.nav-tab.active .tab-icon i{color:#fff}
.nav-tab.active .tab-label{max-width:90px;margin-left:6px;opacity:1}

/* drawer */
.drawer-overlay{position:fixed;inset:0;z-index:200;background:rgba(26,26,24,0);pointer-events:none;transition:background .3s}
.drawer-overlay.open{background:rgba(26,26,24,.5);pointer-events:all}
.drawer{position:fixed;bottom:0;left:0;right:0;transform:translateY(100%);width:100%;z-index:201;background:#fff;border-radius:24px 24px 0 0;padding:0 0 calc(20px + env(safe-area-inset-bottom));transition:transform .35s cubic-bezier(.32,1,.36,1);max-height:92svh;display:flex;flex-direction:column}
.drawer.open{transform:translateY(0)}
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

/* ── popup tab ── */
.popup-pane{padding:4px 0 32px}
.popup-hint{font-size:13px;color:#9a9688;margin-bottom:14px;line-height:1.55}
.popup-btn-row{display:flex;gap:10px;margin:0 0 14px}
.popup-act-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:7px;padding:13px 0;border-radius:12px;background:#f0ece6;border:none;font-size:14px;font-weight:500;color:#3a3830;cursor:pointer;position:relative;overflow:hidden;-webkit-tap-highlight-color:transparent}
.popup-act-btn:active{background:#e4e0da}
.popup-act-btn i{font-size:18px;color:#3a3830;flex-shrink:0}
.popup-ocr-status{font-size:12px;color:#9a9688;margin-bottom:12px;padding:8px 12px;background:#f8f6f2;border-radius:8px}
.popup-content-area{margin-bottom:14px}
.popup-img-preview{width:100%;max-height:340px;object-fit:contain;display:block;border-radius:13px;background:#f0ece6}
.popup-textarea{width:100%;min-height:120px;padding:12px;border-radius:13px;border:1.5px solid #e8e4de;font-size:14px;color:#1a1a18;line-height:1.5;resize:none;font-family:inherit;background:#faf9f7;outline:none;-webkit-appearance:none;display:block;box-sizing:border-box}
.popup-textarea:focus{border-color:#1a1a18}
.popup-summary{background:#f8f6f2;border:1.5px solid #e8e4de;border-radius:13px;padding:14px 14px 12px;margin-bottom:14px}
.ps-name{font-size:16px;font-weight:700;color:#1a1a18;margin-bottom:5px;line-height:1.3}
.ps-meta{font-size:12px;color:#7a7570;margin-bottom:2px;line-height:1.45}
.ps-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.ps-chip{padding:4px 11px;border-radius:12px;font-size:11px;font-weight:600;background:#e8e4de;color:#5a5650;text-transform:capitalize}
.popup-save-btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:15px;border-radius:14px;background:#1a1a18;color:#eceae6;font-size:15px;font-weight:600;cursor:pointer;border:none;margin-top:4px;-webkit-tap-highlight-color:transparent;transition:background .2s,opacity .15s}
.popup-save-btn:active{opacity:.78}
.popup-save-btn.saved-ok{background:#1a7a46}

/* pink card for custom popup classes */
.card-custom-popup{background:linear-gradient(155deg,#2a0818 0%,#160510 72%);background-image:repeating-linear-gradient(35deg,rgba(212,83,126,.1) 0,rgba(212,83,126,.1) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#2a0818 0%,#160510 72%)}
/* manual add form */
.popup-manual-form{background:#f8f6f2;border:1.5px solid #e8e4de;border-radius:16px;padding:16px;margin-bottom:16px;display:flex;flex-direction:column;gap:12px}
.pmf-row{display:flex;gap:10px}
.pmf-field{display:flex;flex-direction:column;gap:5px;flex:1;min-width:0}
.pmf-label{font-size:11px;font-weight:600;color:#9a9688;text-transform:uppercase;letter-spacing:.07em}
.pmf-input{padding:10px 12px;border-radius:10px;border:1.5px solid #e8e4de;font-size:14px;color:#1a1a18;font-family:inherit;background:#fff;outline:none;width:100%;box-sizing:border-box;-webkit-appearance:none}
.pmf-input:focus{border-color:#1a1a18}
.pmf-chips{display:flex;flex-wrap:wrap;gap:6px}
.pmf-chip{padding:7px 13px;border-radius:16px;font-size:12px;font-weight:500;color:#3a3830;background:#f0ece6;border:1.5px solid transparent;cursor:pointer;-webkit-tap-highlight-color:transparent}
.pmf-chip.active{background:#1a1a18;color:#eceae6}
.pmf-save{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:14px;border-radius:13px;background:#1a1a18;color:#eceae6;font-size:15px;font-weight:600;cursor:pointer;border:none;-webkit-tap-highlight-color:transparent;transition:background .2s}
.pmf-save.ok{background:#1a7a46}
/* custom classes list in popup tab */
.popup-classes-header{font-size:12px;font-weight:600;color:#9a9688;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px;margin-top:4px}

/* custom card badge */
.custom-tag{font-size:9px;font-weight:700;letter-spacing:.08em;color:rgba(255,210,80,.95);text-transform:uppercase;background:rgba(255,210,80,.14);border-radius:3px;padding:1px 5px;margin-right:5px;flex-shrink:0;vertical-align:middle}
/* stamp watermark */
.stamp-mark{position:absolute;right:14px;top:50%;pointer-events:none;transform-origin:center center;width:120px;height:120px;}
.stamp-mark img{width:100%;height:100%;display:block;mix-blend-mode:multiply;}
@keyframes stampPress{
  0%  {transform:translateY(-50%) rotate(var(--sr)) scale(calc(var(--ss)*1.35));opacity:0}
  30% {transform:translateY(-50%) rotate(var(--sr)) scale(calc(var(--ss)*0.9));opacity:calc(var(--so)*1.5)}
  60% {transform:translateY(-50%) rotate(var(--sr)) scale(calc(var(--ss)*1.04));opacity:var(--so)}
  100%{transform:translateY(-50%) rotate(var(--sr)) scale(var(--ss));opacity:var(--so)}
}
.stamp-mark.stamp-enter{animation:stampPress .42s cubic-bezier(.22,.68,0,1.2) both}
.stamp-mark.stamp-show{transform:translateY(-50%) rotate(var(--sr)) scale(var(--ss));opacity:var(--so)}
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
            <i class="ph ph-funnel"></i>
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

  <nav id="bottomNav">
    <div id="navBar" class="nav-bar">
      <div id="navCapsule" class="nav-capsule"></div>
      <button class="nav-tab active" data-tab="schedule" id="navSchedule">
        <span class="tab-icon"><i class="ph ph-calendar"></i></span>
        <span class="tab-label">Schedule</span>
      </button>
      <button class="nav-tab" data-tab="popup" id="navPopup">
        <span class="tab-icon"><i class="ph ph-sparkle"></i></span>
        <span class="tab-label">Pop up</span>
      </button>
      <button class="nav-tab" data-tab="wishlist" id="navWishlist">
        <span class="tab-icon"><i class="ph ph-shooting-star"></i></span>
        <span class="tab-label">Wishlist</span>
      </button>
      <button class="nav-tab" data-tab="myclasses" id="navMyclasses">
        <span class="tab-icon"><i class="ph ph-stamp"></i></span>
        <span class="tab-label">My Classes</span>
      </button>
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
      <div class="fsection-label">Style</div>
      <div class="fchip-row" id="genreChipRow">
        <button class="fchip active" data-genre="street"><span class="gdot" style="background:#6b3fa0"></span>Street</button>
        <button class="fchip" data-genre="ballet"><span class="gdot" style="background:#1a6e38"></span>Ballet</button>
        <button class="fchip active" data-genre="contemporary"><span class="gdot" style="background:#1a3a7a"></span>Contemporary</button>
        <button class="fchip active" data-genre="afro"><span class="gdot" style="background:#b87c1a"></span>Afrobeats</button>
        <button class="fchip" data-genre="latin"><span class="gdot" style="background:#9a1a1a"></span>Latin</button>
        <button class="fchip" data-genre="heels"><span class="gdot" style="background:#9a1a4a"></span>Heels</button>
        <button class="fchip active" data-genre="choreo"><span class="gdot" style="background:#0e6e72"></span>Choreo</button>
        <button class="fchip active" data-genre="conditioning"><span class="gdot" style="background:#6e5a3a"></span>Conditioning</button>
        <button class="fchip active" data-genre="other"><span class="gdot" style="background:#5a5040"></span>Other</button>
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
      <div class="fsection-label">Level</div>
      <div class="fchip-row" id="levelChipRow">
        <button class="fchip" data-level="all">All</button>
        <button class="fchip" data-level="Beginner">Beginner</button>
        <button class="fchip active" data-level="All Levels">Open</button>
        <button class="fchip active" data-level="Intermediate">Intermediate</button>
        <button class="fchip active" data-level="Int/Adv">Int/Adv</button>
        <button class="fchip" data-level="Advanced">Advanced</button>
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

// ── custom (popup-added) classes ──
let CUSTOM_CLASSES = JSON.parse(localStorage.getItem('nyd_custom')||'[]');

// ── popup: JS genre extractor (mirrors Python extract_genre) ──
function extractGenreJS(n){
  n=n.toLowerCase();
  if(/ballet|pointe|floor.?barre|rommett/.test(n))return['ballet','classical'];
  if(/vogue|new way|old way/.test(n))return['street','vogue'];
  if(/waack|whack|disco/.test(n))return['street','waacking'];
  if(/\bhouse\b/.test(n))return['street','house'];
  if(/breaking|bboy|bgirl|breakdanc/.test(n))return['street','breaking'];
  if(/popping/.test(n))return['street','popping'];
  if(/locking/.test(n))return['street','locking'];
  if(/afro|african|amapiano/.test(n))return['afro','afrobeats'];
  if(/contemporary|contemp/.test(n))return['contemporary','contemporary'];
  if(/\bmodern\b/.test(n))return['contemporary','modern'];
  if(/jazz.?funk|street.?jazz/.test(n))return['street','jazzfunk'];
  if(/kpop|k-pop/.test(n))return['street','kpop'];
  if(/salsa|mambo|bachata|latin|tango|cumbia|reggaeton/.test(n))return['latin','latin'];
  if(/heel|femme|stiletto/.test(n))return['heels','heels'];
  if(/choreo/.test(n))return['choreo','choreo'];
  if(/hip.?hop/.test(n))return['street','hiphop'];
  if(/street.?style|urban|funk.?style/.test(n))return['street','street'];
  if(/jazz/.test(n))return['contemporary','jazz'];
  if(/yoga|condition|pilates|stretch/.test(n))return['conditioning','conditioning'];
  return['other','other'];
}

// ── popup: JS level extractor ──
function extractLevelJS(n){
  n=n.toLowerCase();
  if(/adv\.?\s*beg|beg\.?\/adv|absolute.?beginner/.test(n))return'Beginner';
  if(/beginner|\bbeg\b/.test(n))return'Beginner';
  if(/all.?level|open.?level|open.?class/.test(n))return'All Levels';
  if(/int\.?\/adv|int\/adv/.test(n))return'Int/Adv';
  if(/intermediate|\binter\b|\bint\b/.test(n))return'Intermediate';
  if(/advanced|\badv\b/.test(n))return'Advanced';
  return'All Levels';
}

// ── popup: parse class text → class object ──
function parseClassText(text){
  if(!text.trim())return null;
  const t=text.trim(),tl=t.toLowerCase();
  const MON={jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12,
    january:1,february:2,march:3,april:4,june:6,july:7,august:8,september:9,october:10,november:11,december:12};
  // Date
  let date_key='';
  const dm=t.match(/(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*[,\s]+([A-Z][a-z]+)\s+(\d{1,2})(?:[,\s]+(\d{4}))?/i)
           ||t.match(/([A-Z][a-z]{2,8})\s+(\d{1,2})(?:[,\s]+(\d{4}))?/i)
           ||t.match(/(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?/);
  if(dm){
    const now=new Date();let m,d,y=now.getFullYear();
    if(isNaN(dm[1])){
      m=MON[dm[1].toLowerCase().slice(0,3)]||(now.getMonth()+1);d=parseInt(dm[2]);
      if(dm[3])y=parseInt(dm[3]);if(y<100)y+=2000;
    }else{m=parseInt(dm[1]);d=parseInt(dm[2]);if(dm[3])y=parseInt(dm[3]);if(y<100)y+=2000;}
    if(d>=1&&d<=31&&m>=1&&m<=12)
      date_key=`${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
  }
  // Time
  let start_display='',start_hour=-1;
  const tm=t.match(/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)/i);
  if(tm){
    let h=parseInt(tm[1]),mn=parseInt(tm[2]||'0'),ap=tm[3].toUpperCase();
    start_display=`${h}:${String(mn).padStart(2,'0')} ${ap}`;
    if(ap==='PM'&&h<12)h+=12;if(ap==='AM'&&h===12)h=0;
    start_hour=h+mn/60;
  }
  // Instructor
  let instructor='';
  const im=t.match(/(?:with|taught by|instructor:?|teacher:?)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)/i);
  if(im)instructor=im[1].trim();
  // Studio
  let studio='Custom';
  const sm=t.match(/(?:@|(?:^|\n)at )\s*([A-Za-z][A-Za-z &']+?)(?:\n|,|\.|$)/m);
  if(sm)studio=sm[1].trim().slice(0,40);
  // Level + genre
  const level=extractLevelJS(tl);
  const[genre,subgenre]=extractGenreJS(tl);
  // Class name: first meaningful line
  const lines=t.split(/\n/).map(l=>l.trim()).filter(l=>l.length>2);
  let class_name=lines[0]||t.slice(0,80);
  if(class_name.length>80)class_name=class_name.slice(0,77)+'…';
  return{studio,studio_key:'custom',class_name,instructor,date_key,
    start_display,end_display:'',duration_min:null,level,genre,subgenre,
    start_hour,is_canceled:false,is_custom:true,booking_url:'',raw_text:t,
    custom_id:`c_${Date.now()}`,saved_at:new Date().toISOString()};
}

// ── popup: auto-fill form from parsed class ──
// ── popup: shared parsed state ──
let _popupParsed=null;

function _showParsedSummary(cls){
  const sd=document.getElementById('popupSummary');
  const sb=document.getElementById('popupSaveBtn');
  if(!sd||!sb)return;
  _popupParsed=cls;
  const dateStr=cls.date_key?formatDateFull(cls.date_key):'';
  const timePart=cls.start_display?' · '+cls.start_display:'';
  const datePart=dateStr?' · '+dateStr:'';
  sd.style.display='';
  sd.innerHTML=`<div class="ps-name">${esc(cls.class_name||'Class')}</div>`
    +`<div class="ps-meta">${esc(cls.studio)}${datePart}${timePart}</div>`
    +(cls.instructor?`<div class="ps-meta">with ${esc(cls.instructor)}</div>`:'')
    +`<div class="ps-chips"><span class="ps-chip">${esc(cls.level)}</span><span class="ps-chip">${esc(cls.genre)}</span></div>`;
  sb.style.display='';
}

// ── popup: save custom class ──
function doSaveCustomClass(){
  if(!_popupParsed)return;
  const cls={..._popupParsed,custom_id:`c_${Date.now()}`,saved_at:new Date().toISOString()};
  CUSTOM_CLASSES.push(cls);
  localStorage.setItem('nyd_custom',JSON.stringify(CUSTOM_CLASSES));
  const btn=document.getElementById('popupSaveBtn');
  if(btn){
    btn.textContent='✓ Saved to Wishlist';btn.classList.add('saved-ok');
    setTimeout(()=>{
      _popupParsed=null;
      const ca=document.getElementById('popupContent');
      const sd=document.getElementById('popupSummary');
      if(ca){ca.style.display='none';ca.innerHTML='';}
      if(sd){sd.style.display='none';sd.innerHTML='';}
      btn.innerHTML='<i class="ph ph-bookmark-simple"></i> Save to Wishlist';
      btn.classList.remove('saved-ok');btn.style.display='none';
    },2000);
  }
}

// ── popup: crop image to strip phone status bar + home indicator, then OCR ──
function cropImageForOcr(file){
  return new Promise(resolve=>{
    const img=new Image();
    img.onload=()=>{
      // Skip top ~8% (status bar: clock, battery, carrier) and bottom ~4% (home indicator)
      const cropTop=Math.floor(img.height*0.08);
      const cropBot=Math.floor(img.height*0.04);
      const h=img.height-cropTop-cropBot;
      const canvas=document.createElement('canvas');
      canvas.width=img.width;canvas.height=h;
      canvas.getContext('2d').drawImage(img,0,-cropTop);
      canvas.toBlob(b=>resolve(b||file),'image/jpeg',0.92);
    };
    img.onerror=()=>resolve(file);
    img.src=URL.createObjectURL(file);
  });
}
function cleanOcrText(raw){
  return raw.split('\n').filter(line=>{
    const t=line.trim();
    if(!t||t.length<=2)return false;
    if(/^\d{1,2}:\d{2}$/.test(t))return false;      // "9:41" — status bar clock
    if(/^\d{1,3}%$/.test(t))return false;            // "87%" — battery
    if(/^[•●■\|\-\._]{1,5}$/.test(t))return false; // signal dots/dashes
    return true;
  }).join('\n').trim();
}
async function handlePopupPhoto(e){
  const file=e.target.files[0];if(!file)return;
  const imgUrl=URL.createObjectURL(file);
  // Show image preview immediately
  const ca=document.getElementById('popupContent');
  if(ca){
    ca.style.display='';
    ca.innerHTML=`<img src="${imgUrl}" class="popup-img-preview" alt="Class photo"/>`;
  }
  const status=document.getElementById('popupOcrStatus');
  if(status){status.style.display='';status.textContent='Reading text from photo…';}
  try{
    if(!window.Tesseract){
      await new Promise((res,rej)=>{const s=document.createElement('script');
        s.src='https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js';
        s.onload=res;s.onerror=rej;document.head.appendChild(s);});
    }
    const cropped=await cropImageForOcr(file);
    const{data:{text}}=await Tesseract.recognize(cropped,'eng',{logger:()=>{}});
    const cleaned=cleanOcrText(text);
    if(status)status.style.display='none';
    const cls=parseClassText(cleaned);
    if(cls)_showParsedSummary(cls);
    else{
      // OCR got no parseable data — still let user save with placeholder
      _showParsedSummary({studio:'Custom',studio_key:'custom',class_name:'Custom Class',
        instructor:'',date_key:'',start_display:'',end_display:'',level:'All Levels',
        genre:'other',subgenre:'other',start_hour:-1,is_canceled:false,is_custom:true,
        booking_url:'',raw_text:cleaned});
    }
  }catch(err){
    if(status){status.style.display='';status.textContent='Could not read text — saving photo as custom class.';}
    _showParsedSummary({studio:'Custom',studio_key:'custom',class_name:'Custom Class',
      instructor:'',date_key:'',start_display:'',end_display:'',level:'All Levels',
      genre:'other',subgenre:'other',start_hour:-1,is_canceled:false,is_custom:true,
      booking_url:'',raw_text:''});
  }
}

// ── popup tab render ──
function renderManualForm(container){
  // Build instructor and studio lists from ALL_CLASSES
  const instructors=[...new Set(ALL_CLASSES.filter(c=>c.instructor&&c.instructor!=='Modega Staff').map(c=>c.instructor))].sort();
  const studios=[...new Set(ALL_CLASSES.map(c=>c.studio))].sort();
  const GENRE_LABELS={street:'Street',ballet:'Ballet',contemporary:'Contemporary',afro:'Afro',latin:'Latin',heels:'Heels',choreo:'Choreo',conditioning:'Conditioning',other:'Other'};
  const LEVEL_LABELS=['All Levels','Beginner','Intermediate','Int/Adv','Advanced'];

  container.innerHTML=`
<div class="popup-manual-form" id="pmfWrap">
  <datalist id="pmf-instrs">${instructors.map(i=>`<option value="${esc(i)}">`).join('')}</datalist>
  <datalist id="pmf-studios">${studios.map(s=>`<option value="${esc(s)}">`).join('')}</datalist>
  <div class="pmf-field">
    <label class="pmf-label">Class name</label>
    <input class="pmf-input" id="pmf_name" list="pmf-instrs" placeholder="e.g. Heels Fundamentals" autocomplete="off"/>
  </div>
  <div class="pmf-row">
    <div class="pmf-field">
      <label class="pmf-label">Instructor</label>
      <input class="pmf-input" id="pmf_instructor" list="pmf-instrs" placeholder="Name" autocomplete="off"/>
    </div>
    <div class="pmf-field">
      <label class="pmf-label">Studio / Location</label>
      <input class="pmf-input" id="pmf_studio" list="pmf-studios" placeholder="Studio" autocomplete="off"/>
    </div>
  </div>
  <div class="pmf-row">
    <div class="pmf-field">
      <label class="pmf-label">Date</label>
      <input class="pmf-input" id="pmf_date" type="date"/>
    </div>
    <div class="pmf-field">
      <label class="pmf-label">Time</label>
      <input class="pmf-input" id="pmf_time" type="time"/>
    </div>
  </div>
  <div class="pmf-field">
    <label class="pmf-label">Style</label>
    <div class="pmf-chips" id="pmf_genre_chips">
      ${Object.entries(GENRE_LABELS).map(([k,v])=>`<button class="pmf-chip" data-val="${k}">${v}</button>`).join('')}
    </div>
  </div>
  <div class="pmf-field">
    <label class="pmf-label">Level</label>
    <div class="pmf-chips" id="pmf_level_chips">
      ${LEVEL_LABELS.map(l=>`<button class="pmf-chip${l==='All Levels'?' active':''}" data-val="${l}">${l}</button>`).join('')}
    </div>
  </div>
  <button class="pmf-save" id="pmfSaveBtn"><i class="ph ph-plus-circle"></i> Add Class</button>
</div>`;

  // Chip toggles (genre: single, level: single)
  ['pmf_genre_chips','pmf_level_chips'].forEach(rowId=>{
    container.querySelectorAll(`#${rowId} .pmf-chip`).forEach(ch=>{
      ch.addEventListener('click',()=>{
        container.querySelectorAll(`#${rowId} .pmf-chip`).forEach(x=>x.classList.remove('active'));
        ch.classList.add('active');
      });
    });
  });

  container.querySelector('#pmfSaveBtn').addEventListener('click',()=>{
    const name=(container.querySelector('#pmf_name').value||'').trim()||'Custom Class';
    const instructor=(container.querySelector('#pmf_instructor').value||'').trim();
    const studio=(container.querySelector('#pmf_studio').value||'').trim()||'Custom';
    const dateVal=container.querySelector('#pmf_date').value||'';
    const timeVal=container.querySelector('#pmf_time').value||'';
    const genreEl=container.querySelector('#pmf_genre_chips .pmf-chip.active');
    const genre=genreEl?genreEl.dataset.val:'other';
    const levelEl=container.querySelector('#pmf_level_chips .pmf-chip.active');
    const level=levelEl?levelEl.dataset.val:'All Levels';
    let start_display='',start_hour=-1;
    if(timeVal){
      const[hh,mm]=timeVal.split(':').map(Number);
      const period=hh>=12?'PM':'AM';const dh=hh>12?hh-12:(hh===0?12:hh);
      start_display=`${dh}:${String(mm).padStart(2,'0')} ${period}`;
      start_hour=hh+mm/60;
    }
    const[sg]=extractGenreJS(name.toLowerCase());
    const cls={studio,studio_key:'custom',class_name:name,instructor,date_key:dateVal,
      start_display,end_display:'',level,genre:genre||sg,subgenre:genre||sg,
      start_hour,is_canceled:false,is_custom:true,booking_url:'',raw_text:'',
      custom_id:`c_${Date.now()}`,saved_at:new Date().toISOString()};
    CUSTOM_CLASSES.push(cls);
    localStorage.setItem('nyd_custom',JSON.stringify(CUSTOM_CLASSES));
    const btn=container.querySelector('#pmfSaveBtn');
    btn.textContent='✓ Added!';btn.classList.add('ok');
    setTimeout(()=>{renderPopup();},1200);
  });
}

function renderPopup(){
  _popupParsed=null;
  document.getElementById('pageTitle').textContent='Pop up';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  const listEl=document.getElementById('classesList');

  // Sort CUSTOM_CLASSES by date desc (most recent first)
  const sorted=[...CUSTOM_CLASSES].sort((a,b)=>b.date_key.localeCompare(a.date_key));
  const customListHTML=sorted.length?`
<div class="popup-classes-header">Your Pop-ups (${sorted.length})</div>
<div id="popupCustomList"></div>`:'';

  listEl.innerHTML=`
<div class="popup-pane">
  <div class="popup-btn-row" style="gap:8px">
    <button class="popup-act-btn" id="popupPasteBtn" style="flex:1">
      <i class="ph ph-clipboard-text"></i>Paste
    </button>
    <label class="popup-act-btn" style="flex:1;cursor:pointer">
      <i class="ph ph-camera"></i>Photo
      <input type="file" id="popupPhotoInput" accept="image/*" style="position:absolute;opacity:0;width:0;height:0;pointer-events:none"/>
    </label>
    <button class="popup-act-btn" id="popupManualBtn" style="flex:1">
      <i class="ph ph-pencil-simple"></i>Manual
    </button>
  </div>
  <div id="popupOcrStatus" class="popup-ocr-status" style="display:none"></div>
  <div id="popupManualWrap"></div>
  <div id="popupContent" class="popup-content-area" style="display:none"></div>
  <div id="popupSummary" class="popup-summary" style="display:none"></div>
  <button class="popup-save-btn" id="popupSaveBtn" style="display:none">
    <i class="ph ph-bookmark-simple"></i>Save to Wishlist
  </button>
  ${customListHTML}
</div>`;

  // Render custom class cards
  if(sorted.length){
    const cl=listEl.querySelector('#popupCustomList');
    sorted.forEach((c,i)=>cl.appendChild(buildCard(c,i)));
  }

  // Manual form toggle
  let manualOpen=false;
  document.getElementById('popupManualBtn').addEventListener('click',()=>{
    manualOpen=!manualOpen;
    const wrap=document.getElementById('popupManualWrap');
    if(manualOpen){renderManualForm(wrap);}
    else{wrap.innerHTML='';}
  });

  // Paste button
  document.getElementById('popupPasteBtn').addEventListener('click',async()=>{
    const status=document.getElementById('popupOcrStatus');
    try{
      const text=await navigator.clipboard.readText();
      if(text){
        const ca=document.getElementById('popupContent');
        ca.style.display='';
        ca.innerHTML=`<textarea class="popup-textarea" readonly>${esc(text)}</textarea>`;
        const cls=parseClassText(text);
        if(cls)_showParsedSummary(cls);
      }
    }catch(e){
      const ca=document.getElementById('popupContent');
      ca.style.display='';
      ca.innerHTML='<textarea id="popupManualTA" class="popup-textarea" placeholder="Paste your text here…"></textarea>';
      document.getElementById('popupManualTA').focus();
      document.getElementById('popupManualTA').addEventListener('input',function(){
        clearTimeout(window._ppD);
        window._ppD=setTimeout(()=>{
          const cls=parseClassText(this.value);
          if(cls)_showParsedSummary(cls);
        },600);
      });
      if(status){status.style.display='';status.textContent='Tap & hold the box above, then choose Paste.';
        setTimeout(()=>{status.style.display='none';},4000);}
    }
  });

  document.getElementById('popupPhotoInput').addEventListener('change',handlePopupPhoto);
  document.getElementById('popupSaveBtn').addEventListener('click',doSaveCustomClass);
}

// ── bookmarks ──
function classId(c){return c.date_key+'|'+c.studio_key+'|'+c.class_name+'|'+c.start_display}
let savedSet=new Set(JSON.parse(localStorage.getItem('nyd_saved')||'[]'));
function isSaved(c){return savedSet.has(classId(c))}
function toggleSaved(c){
  const id=classId(c);let now;
  if(savedSet.has(id)){savedSet.delete(id);now=false}else{savedSet.add(id);now=true}
  localStorage.setItem('nyd_saved',JSON.stringify([...savedSet]));
  sbSyncWishlist();
  return now;
}

// ── my classes ──
let myClassesMap=(()=>{
  const raw=JSON.parse(localStorage.getItem('nyd_my_classes')||'{}');
  // migrate: notes string → array
  Object.values(raw).forEach(v=>{if(typeof v.notes==='string')v.notes=v.notes?[{id:'n0',text:v.notes,type:'text',created_at:v.added_at}]:[];});
  return raw;
})();
// ── Supabase ────────────────────────────────────────────────────────────────
// Fill in YOUR project URL and anon key after creating the Supabase project.
// Auth will be added later; all data is tied to this mock user ID.
//
// SQL schema (run in Supabase SQL editor):
// create table if not exists my_classes(user_id text, class_id text, class_json jsonb, added_at timestamptz default now(), primary key(user_id,class_id));
// create table if not exists notes(user_id text, note_id text, class_id text, text text, type text, created_at timestamptz default now(), primary key(user_id,note_id));
// create table if not exists wishlist(user_id text, class_id text, class_json jsonb, saved_at timestamptz default now(), primary key(user_id,class_id));
// create table if not exists custom_classes(user_id text, class_id text, class_json jsonb, created_at timestamptz default now(), primary key(user_id,class_id));
// create table if not exists user_preferences(user_id text, pref_key text, value_json text, updated_at timestamptz default now(), primary key(user_id,pref_key));
const _SB_URL='https://riezaxehqtoaxjysguwe.supabase.co';
const _SB_KEY='sb_publishable_beWZ6S96-qf51IBebC_IVQ_ufUR_E9_';
const _SB_USER='yunshroom-test-01';
let _sb=null;
let _remoteClassIds=new Set(); // tracks which class_ids exist in Supabase so we can delete removed ones
(function(){
  try{
    if(_SB_URL&&typeof supabase!=='undefined'){
      _sb=supabase.createClient(_SB_URL,_SB_KEY);
      console.log('[Supabase] connected');
    } else {
      console.log('[Supabase] not configured yet — running in local-only mode');
    }
  }catch(e){console.warn('[Supabase] init error',e);}
})();

async function sbSyncMyClasses(){
  if(!_sb)return;
  try{
    const currentIds=new Set(Object.keys(myClassesMap));
    // Delete any classes that were in Supabase but have been removed locally
    const toDelete=[..._remoteClassIds].filter(id=>!currentIds.has(id));
    if(toDelete.length){
      await _sb.from('my_classes').delete().eq('user_id',_SB_USER).in('class_id',toDelete);
      toDelete.forEach(id=>_remoteClassIds.delete(id));
    }
    // Upsert current state
    const rows=Object.entries(myClassesMap).map(([id,v])=>({user_id:_SB_USER,class_id:id,class_json:v,added_at:v.added_at}));
    if(rows.length){
      await _sb.from('my_classes').upsert(rows,{onConflict:'user_id,class_id'});
      currentIds.forEach(id=>_remoteClassIds.add(id));
    }
  }catch(e){console.warn('[Supabase] sbSyncMyClasses error',e);}
}
async function sbSyncNotes(classId){
  if(!_sb)return;
  try{
    const entry=myClassesMap[classId];if(!entry)return;
    const rows=(entry.notes||[]).map(n=>({user_id:_SB_USER,note_id:n.id,class_id:classId,text:n.text,type:n.type,created_at:n.created_at}));
    // delete removed notes then upsert current
    await _sb.from('notes').delete().eq('user_id',_SB_USER).eq('class_id',classId);
    if(rows.length)await _sb.from('notes').upsert(rows,{onConflict:'user_id,note_id'});
  }catch(e){console.warn('[Supabase] sbSyncNotes error',e);}
}
async function sbSyncWishlist(){
  if(!_sb)return;
  try{
    const ids=JSON.parse(localStorage.getItem('nyd_saved')||'[]');
    const rows=ids.map(id=>({user_id:_SB_USER,class_id:id,saved_at:new Date().toISOString()}));
    await _sb.from('wishlist').delete().eq('user_id',_SB_USER);
    if(rows.length)await _sb.from('wishlist').upsert(rows,{onConflict:'user_id,class_id'});
  }catch(e){console.warn('[Supabase] sbSyncWishlist error',e);}
}
async function sbSyncCustomClasses(){
  if(!_sb)return;
  try{
    const rows=CUSTOM_CLASSES.map(c=>({user_id:_SB_USER,class_id:classId(c),class_json:c,created_at:new Date().toISOString()}));
    await _sb.from('custom_classes').delete().eq('user_id',_SB_USER);
    if(rows.length)await _sb.from('custom_classes').upsert(rows,{onConflict:'user_id,class_id'});
  }catch(e){console.warn('[Supabase] sbSyncCustomClasses error',e);}
}
async function sbSyncFavTeachers(){
  if(!_sb)return;
  try{
    const val=JSON.stringify([...favTeachers]);
    await _sb.from('user_preferences').upsert([{user_id:_SB_USER,pref_key:'fav_teachers',value_json:val}],{onConflict:'user_id,pref_key'});
  }catch(e){console.warn('[Supabase] sbSyncFavTeachers error',e);}
}
async function sbSyncFilters(){
  if(!_sb)return;
  try{
    const val=JSON.stringify(_serializeFilters());
    await _sb.from('user_preferences').upsert([{user_id:_SB_USER,pref_key:'filters',value_json:val}],{onConflict:'user_id,pref_key'});
  }catch(e){console.warn('[Supabase] sbSyncFilters error',e);}
}
async function sbLoadAll(){
  if(!_sb)return;
  try{
    // ── my_classes: Supabase is source of truth ──
    // Local data is only used as fallback when Supabase has nothing at all.
    // We never push local-only items up — that would resurrect deleted classes.
    const{data:mc,error:mcErr}=await _sb.from('my_classes').select('class_id,class_json,added_at').eq('user_id',_SB_USER);
    if(mcErr)console.warn('[Supabase] my_classes fetch error',mcErr);
    const{data:notes}=await _sb.from('notes').select('*').eq('user_id',_SB_USER);
    _remoteClassIds=new Set((mc||[]).map(r=>r.class_id));
    if(mc&&mc.length){
      // Replace local state entirely with what Supabase has
      const remote={};
      mc.forEach(row=>{
        remote[row.class_id]={notes:[],added_at:row.added_at,...(row.class_json||{})};
        remote[row.class_id].notes=[];
      });
      // Attach notes from Supabase
      (notes||[]).forEach(n=>{
        if(remote[n.class_id])remote[n.class_id].notes.push({id:n.note_id,text:n.text,type:n.type,created_at:n.created_at});
      });
      Object.keys(myClassesMap).forEach(k=>delete myClassesMap[k]);
      Object.assign(myClassesMap,remote);
      localStorage.setItem('nyd_my_classes',JSON.stringify(myClassesMap));
    }
    // (if Supabase has no data, keep localStorage as-is — first-time device)
    // ── wishlist: Supabase is source of truth ──
    const{data:wl}=await _sb.from('wishlist').select('class_id').eq('user_id',_SB_USER);
    if(wl&&wl.length){
      savedSet.clear();
      wl.forEach(r=>savedSet.add(r.class_id));
      localStorage.setItem('nyd_saved',JSON.stringify([...savedSet]));
    }
    // ── custom classes ──
    const{data:cc}=await _sb.from('custom_classes').select('class_json').eq('user_id',_SB_USER);
    if(cc&&cc.length){
      const arr=cc.map(r=>r.class_json);
      localStorage.setItem('nyd_custom',JSON.stringify(arr));
      CUSTOM_CLASSES.length=0;arr.forEach(c=>CUSTOM_CLASSES.push(c));
    }
    // ── preferences: fav teachers + filters ──
    const{data:prefs}=await _sb.from('user_preferences').select('pref_key,value_json').eq('user_id',_SB_USER);
    (prefs||[]).forEach(p=>{
      if(p.pref_key==='fav_teachers'){
        try{const arr=JSON.parse(p.value_json);favTeachers=new Set(arr);localStorage.setItem('nyd_fav_t',p.value_json);}catch(e){}
      }
      if(p.pref_key==='filters'){
        try{const f=JSON.parse(p.value_json);_applySerializedFilters(f);localStorage.setItem('nyd_filters',p.value_json);}catch(e){}
      }
    });
    console.log('[Supabase] sync complete — my_classes:',Object.keys(myClassesMap).length,'wishlist:',savedSet.size);
    if(typeof syncChipsFromState==='function')syncChipsFromState();
    if(typeof renderAll==='function')renderAll();
  }catch(e){console.warn('[Supabase] sbLoadAll error',e);}
}
// Load remote data on startup (fire-and-forget; local data shown first)
sbLoadAll();

// myClassesMap: {classId → {notes, added_at}}
function isMyClass(c){return!!myClassesMap[classId(c)]}
function toggleMyClass(c){
  const id=classId(c);
  if(myClassesMap[id]){delete myClassesMap[id];}
  else{myClassesMap[id]={notes:[],added_at:new Date().toISOString()};}
  localStorage.setItem('nyd_my_classes',JSON.stringify(myClassesMap));
  sbSyncMyClasses();
  return!!myClassesMap[id];
}
function addNote(c,text,type){
  const id=classId(c);
  if(!myClassesMap[id])return;
  const note={id:`n_${Date.now()}`,text,type,created_at:new Date().toISOString()};
  myClassesMap[id].notes.push(note);
  localStorage.setItem('nyd_my_classes',JSON.stringify(myClassesMap));
  return note;
}
function deleteNote(c,noteId){
  const id=classId(c);
  if(!myClassesMap[id])return;
  myClassesMap[id].notes=myClassesMap[id].notes.filter(n=>n.id!==noteId);
  localStorage.setItem('nyd_my_classes',JSON.stringify(myClassesMap));
}

let _notesClass=null;

const STICKY_COLORS=[
  {bg:'#fffdf5',tape:'rgba(212,83,126,0.55)'},
  {bg:'#f0f7ff',tape:'rgba(120,160,220,0.55)'},
  {bg:'#f5fff0',tape:'rgba(99,153,34,0.55)'},
  {bg:'#fff8f0',tape:'rgba(186,117,23,0.55)'},
  {bg:'#f3f2ff',tape:'rgba(127,119,221,0.55)'},
];
const NOTE_ROTS=[-1.4,-0.7,0.6,1.3,-0.3,0.9,-1.1,0.4];
function stickyColor(idx){return STICKY_COLORS[idx%STICKY_COLORS.length];}
function noteRot(idx){return NOTE_ROTS[idx%NOTE_ROTS.length];}

function renderNoteDetail(c){
  _notesClass=c;
  const id=classId(c);
  const listEl=document.getElementById('classesList');
  listEl.innerHTML='';

  // ── back header ──────────────────────────────────────────────
  const header=document.createElement('div');
  header.style.cssText='display:flex;align-items:center;gap:10px;margin-bottom:14px';
  header.innerHTML=`<button id="notesBackBtn" style="font-size:22px;color:#1a1a18;background:none;border:none;cursor:pointer;display:flex;align-items:center"><i class="ph ph-arrow-left"></i></button>`
    +`<div style="font-family:'Permanent Marker',cursive;font-size:21px;color:#111;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.class_name)}</div>`;
  listEl.appendChild(header);
  document.getElementById('notesBackBtn').addEventListener('click',()=>{_notesClass=null;renderMyClasses();});

  // ── scrapbook container ──────────────────────────────────────
  const scrap=document.createElement('div');
  scrap.style.cssText='background:#eceae6;border-radius:16px;padding:16px;position:relative;overflow:hidden';
  // dot pattern overlay
  const dots=document.createElement('div');
  dots.style.cssText='position:absolute;inset:0;opacity:.22;background-image:radial-gradient(circle,rgba(0,0,0,.33) 1px,transparent 1px);background-size:2.5px 2.5px;pointer-events:none';
  scrap.appendChild(dots);
  // pink glow
  const glow=document.createElement('div');
  glow.style.cssText='position:absolute;top:0;right:0;width:140px;height:140px;background:radial-gradient(circle at 100% 0%,rgba(220,140,170,.35),transparent 70%);pointer-events:none';
  scrap.appendChild(glow);

  // class meta line
  const metaLine=document.createElement('div');
  metaLine.style.cssText='position:relative;margin-bottom:12px';
  const dateStr=c.date_key?c.date_key.slice(5).replace('-','/'):'';
  const instructorStr=c.instructor||'';
  const levelStr=c.level||'';
  metaLine.innerHTML=`<p style="font-family:'DM Mono',monospace;font-size:10px;color:#9a9688;margin:0;text-transform:uppercase;letter-spacing:.04em">${dateStr}${instructorStr?' · '+instructorStr:''}${levelStr?' · '+levelStr:''}</p>`;
  scrap.appendChild(metaLine);

  // divider
  const div=document.createElement('div');
  div.style.cssText='height:.5px;background:rgba(26,26,24,.12);margin-bottom:12px;position:relative';
  scrap.appendChild(div);

  // ── notes cards container ───────────────────────────────────
  const container=document.createElement('div');
  container.id='noteCardsContainer';
  container.style.cssText='display:flex;flex-direction:column;gap:10px;position:relative;min-height:8px';
  scrap.appendChild(container);

  // ── input area ──────────────────────────────────────────────
  const inputArea=document.createElement('div');
  inputArea.id='noteInputArea';
  inputArea.style.cssText='margin-top:12px;position:relative';
  scrap.appendChild(inputArea);
  listEl.appendChild(scrap);

  // ── voice recording state ────────────────────────────────────
  let _isRecording=false;
  let _recognition=null;
  let _pendingTranscript='';

  function _formatNoteTime(){
    const d=new Date();const h=d.getHours();const m=String(d.getMinutes()).padStart(2,'0');
    const ap=h>=12?'PM':'AM';const dh=h%12||12;return`${dh}:${m}${ap}`;
  }

  function _buildSticky(n,i,isNew){
    const col=stickyColor(i);
    const rot=noteRot(i);
    const dt=new Date(n.created_at);
    const mon=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][dt.getMonth()];
    const hh=dt.getHours(),mm=dt.getMinutes(),period=hh>=12?'PM':'AM';
    const dh=hh%12||12;
    const timeStr=`${dh}:${String(mm).padStart(2,'0')} ${period}`;
    const typeLabel=n.type==='voice'?'voice → text':'text';

    const card=document.createElement('div');
    card.className='sticky-note'+(isNew?' note-in':'');
    card.style.cssText=`background:${col.bg};--r:${rot}deg;transform:rotate(${rot}deg);`;

    // tape
    const tape=document.createElement('div');
    tape.className='sticky-tape';
    tape.style.background=col.tape;
    card.appendChild(tape);

    // meta row
    const meta=document.createElement('div');
    meta.style.cssText='display:flex;align-items:center;gap:5px;margin-bottom:5px';
    if(n.type==='voice'){
      meta.innerHTML=`<i class="ph-fill ph-microphone" style="font-size:11px;color:#7f77dd;" aria-hidden="true"></i><span style="font-family:'DM Mono',monospace;font-size:10px;color:#9a9688">${timeStr} · ${typeLabel}</span>`;
    } else {
      meta.innerHTML=`<span style="font-family:'DM Mono',monospace;font-size:10px;color:#9a9688">${timeStr} · ${typeLabel}</span>`;
    }
    card.appendChild(meta);

    // text
    const txt=document.createElement('p');
    txt.style.cssText='font-family:"DM Sans",sans-serif;font-size:13px;color:#2a2820;margin:0;line-height:1.55';
    txt.textContent=n.text;
    card.appendChild(txt);

    // delete
    const del=document.createElement('button');
    del.setAttribute('aria-label','delete note');
    del.style.cssText='position:absolute;top:8px;right:8px;background:none;border:none;cursor:pointer;color:rgba(26,26,24,.25);padding:2px;line-height:1';
    del.innerHTML='<i class="ph ph-x" style="font-size:12px"></i>';
    del.addEventListener('click',()=>{deleteNote(c,n.id);sbSyncNotes(id);_rebuildNotes();});
    card.appendChild(del);
    return card;
  }

  function _rebuildNotes(){
    const notes2=(myClassesMap[id]?.notes)||[];
    container.innerHTML='';
    if(!notes2.length){
      const empty=document.createElement('div');
      empty.style.cssText='color:#9a9688;font-family:"DM Mono",monospace;font-size:11px;padding:6px 0 12px;text-align:center';
      empty.textContent='no notes yet — add one below';
      container.appendChild(empty);
    } else {
      notes2.forEach((n,i)=>container.appendChild(_buildSticky(n,i,false)));
    }
  }

  function _showAddButtons(){
    inputArea.innerHTML='';
    const row=document.createElement('div');
    row.style.cssText='display:flex;gap:8px';
    // text note pill (dark)
    const textBtn=document.createElement('button');
    textBtn.className='note-pill-btn';
    textBtn.style.cssText+='background:rgba(26,26,24,.82);color:#eceae6;';
    textBtn.innerHTML='<i class="ph ph-pencil-simple" style="font-size:14px"></i> text note';
    textBtn.addEventListener('click',_showTextInput);
    row.appendChild(textBtn);
    // voice note pill (purple)
    const voiceBtn=document.createElement('button');
    voiceBtn.className='note-pill-btn';
    voiceBtn.style.cssText+='background:rgba(127,119,221,.85);color:#fff;';
    voiceBtn.innerHTML='<i class="ph ph-microphone" style="font-size:14px"></i> voice note';
    voiceBtn.addEventListener('click',_showVoiceInput);
    row.appendChild(voiceBtn);
    inputArea.appendChild(row);
  }

  function _showTextInput(){
    inputArea.innerHTML='';
    const wrap=document.createElement('div');
    wrap.style.cssText='display:flex;flex-direction:column;gap:8px';
    const box=document.createElement('div');
    box.style.cssText='background:#fffdf5;border-radius:8px;padding:10px 12px;border:1px solid rgba(26,26,24,.1)';
    const ta=document.createElement('textarea');
    ta.id='noteTextTA';
    ta.placeholder='write anything — feelings, techniques, reminders…';
    ta.rows=3;
    ta.style.cssText='width:100%;border:none;background:transparent;font-family:"DM Sans",sans-serif;font-size:13px;color:#1a1a18;resize:none;outline:none;box-sizing:border-box;line-height:1.5';
    box.appendChild(ta);
    wrap.appendChild(box);
    // buttons row
    const btnRow=document.createElement('div');
    btnRow.style.cssText='display:flex;gap:8px;justify-content:flex-end';
    const cancelBtn=document.createElement('button');
    cancelBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#9a9688;background:none;border:none;cursor:pointer;padding:6px 10px';
    cancelBtn.textContent='cancel';
    cancelBtn.addEventListener('click',_showAddButtons);
    const saveBtn=document.createElement('button');
    saveBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#f5f1ea;background:#1a1a18;border:none;border-radius:999px;cursor:pointer;padding:7px 16px';
    saveBtn.textContent='add note';
    saveBtn.addEventListener('click',()=>{
      const text=ta.value.trim();
      if(!text)return;
      const note=addNote(c,text,'text');
      sbSyncNotes(id);
      _rebuildNotes();
      const cards=[...container.children];
      const last=cards[cards.length-1];
      if(last&&last.classList){last.classList.add('note-in');}
      _showAddButtons();
    });
    ta.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))saveBtn.click();});
    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(saveBtn);
    wrap.appendChild(btnRow);
    inputArea.appendChild(wrap);
    setTimeout(()=>ta.focus(),50);
  }

  function _showVoiceInput(){
    inputArea.innerHTML='';
    _pendingTranscript='';
    _isRecording=false;

    const wrap=document.createElement('div');
    wrap.style.cssText='display:flex;flex-direction:column;gap:8px';

    const voiceBox=document.createElement('div');
    voiceBox.style.cssText='background:#f3f2ff;border-radius:8px;padding:14px 12px;border:1px solid rgba(127,119,221,.2);text-align:center';

    const micWrap=document.createElement('div');
    micWrap.id='noteRecBtn';
    micWrap.style.cssText='width:52px;height:52px;border-radius:50%;background:#7f77dd;display:flex;align-items:center;justify-content:center;margin:0 auto 10px;cursor:pointer';
    micWrap.innerHTML='<i id="noteRecIcon" class="ph-fill ph-microphone" style="font-size:22px;color:#fff" aria-hidden="true"></i>';

    const statusP=document.createElement('p');
    statusP.id='noteRecStatus';
    statusP.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#7f77dd;margin:0 0 8px';
    statusP.textContent='tap to record';

    const transcribedWrap=document.createElement('div');
    transcribedWrap.id='noteTranscribedWrap';
    transcribedWrap.style.cssText='display:none;text-align:left;background:#fff;border-radius:6px;padding:8px 10px;margin-bottom:8px';
    transcribedWrap.innerHTML='<p style="font-family:\'DM Mono\',monospace;font-size:10px;color:#9a9688;margin:0 0 4px;text-transform:uppercase;letter-spacing:.04em">voice → text</p><p id="noteTranscribedText" style="font-family:\'DM Sans\',sans-serif;font-size:13px;color:#1a1a18;margin:0"></p>';

    voiceBox.appendChild(micWrap);
    voiceBox.appendChild(statusP);
    voiceBox.appendChild(transcribedWrap);
    wrap.appendChild(voiceBox);

    const btnRow=document.createElement('div');
    btnRow.style.cssText='display:flex;gap:8px;justify-content:flex-end';
    const cancelBtn=document.createElement('button');
    cancelBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#9a9688;background:none;border:none;cursor:pointer;padding:6px 10px';
    cancelBtn.textContent='cancel';
    cancelBtn.addEventListener('click',()=>{_stopRecording();_showAddButtons();});
    const saveVoiceBtn=document.createElement('button');
    saveVoiceBtn.id='noteSaveVoiceBtn';
    saveVoiceBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#fff;background:#7f77dd;border:none;border-radius:999px;cursor:pointer;padding:7px 16px;display:none';
    saveVoiceBtn.textContent='save note';
    saveVoiceBtn.addEventListener('click',()=>{
      if(!_pendingTranscript.trim())return;
      addNote(c,_pendingTranscript.trim(),'voice');
      sbSyncNotes(id);
      _rebuildNotes();
      _showAddButtons();
    });
    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(saveVoiceBtn);
    wrap.appendChild(btnRow);
    inputArea.appendChild(wrap);

    function _updateRecUI(){
      const icon=document.getElementById('noteRecIcon');
      const btn=document.getElementById('noteRecBtn');
      const stat=document.getElementById('noteRecStatus');
      if(!icon||!btn||!stat)return;
      if(_isRecording){
        icon.className='ph-fill ph-stop rec-pulse';
        btn.style.background='#d4537e';
        stat.textContent='recording… tap to stop';
      } else {
        icon.className='ph-fill ph-microphone';
        btn.style.background='#7f77dd';
        if(!_pendingTranscript)stat.textContent='tap to record';
      }
    }

    function _simulateTranscription(){
      _isRecording=true;_updateRecUI();
      const samples=['the footwork in the second 8-count is tricky — drill it slow first','ask about the hip isolation in the bridge section','felt so good today, best class in weeks'];
      const t=samples[Math.floor(Math.random()*samples.length)];
      setTimeout(()=>{
        _pendingTranscript=t;
        const tw=document.getElementById('noteTranscribedWrap');
        const tt=document.getElementById('noteTranscribedText');
        const sv=document.getElementById('noteSaveVoiceBtn');
        const st=document.getElementById('noteRecStatus');
        if(tw)tw.style.display='block';
        if(tt)tt.textContent=t;
        if(sv)sv.style.display='block';
        if(st)st.textContent='transcription complete';
        _isRecording=false;_updateRecUI();
      },2000);
    }

    function _startRecording(){
      const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
      if(!SR){_simulateTranscription();return;}
      _recognition=new SR();
      _recognition.continuous=false;_recognition.interimResults=true;_recognition.lang='en-US';
      _recognition.onresult=e=>{
        let t='';for(let i=e.resultIndex;i<e.results.length;i++)t+=e.results[i][0].transcript;
        _pendingTranscript=t;
        const tw=document.getElementById('noteTranscribedWrap');
        const tt=document.getElementById('noteTranscribedText');
        if(tw)tw.style.display='block';if(tt)tt.textContent=t;
        if(e.results[e.results.length-1].isFinal){
          const sv=document.getElementById('noteSaveVoiceBtn');
          if(sv)sv.style.display='block';
        }
      };
      _recognition.onerror=()=>_simulateTranscription();
      _recognition.onend=()=>{_isRecording=false;_updateRecUI();if(_pendingTranscript){const sv=document.getElementById('noteSaveVoiceBtn');if(sv)sv.style.display='block';}};
      _recognition.start();
      _isRecording=true;_updateRecUI();
    }

    function _stopRecording(){
      if(_recognition){_recognition.stop();_recognition=null;}
      _isRecording=false;_updateRecUI();
    }

    micWrap.addEventListener('click',()=>{if(!_isRecording)_startRecording();else _stopRecording();});
  }

  _rebuildNotes();
  _showAddButtons();
}

function renderMyClasses(){
  if(_notesClass){renderNoteDetail(_notesClass);return;}
  document.getElementById('pageTitle').textContent='My Classes';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  const listEl=document.getElementById('classesList');
  const stamped=[...ALL_CLASSES,...CUSTOM_CLASSES].filter(c=>isMyClass(c));
  if(!stamped.length){
    listEl.innerHTML=`<div class="empty-state"><div class="empty-icon">🎟️</div><div class="empty-title">No classes stamped yet</div><div class="empty-sub">Tap the stamp icon on any class card to add it here.</div></div>`;
    return;
  }
  stamped.sort((a,b)=>a.date_key<b.date_key?-1:a.date_key>b.date_key?1:a.start_hour-b.start_hour);
  listEl.innerHTML='';let lastDate='';
  stamped.forEach((c,i)=>{
    if(c.date_key!==lastDate){
      const div=document.createElement('div');div.className='section-divider date-divider';
      div.innerHTML=`${formatDateFull(c.date_key)}<div class="section-line"></div>`;
      listEl.appendChild(div);lastDate=c.date_key;
    }
    const card=buildCard(c,i);
    // Notes button row below card
    const noteRow=document.createElement('div');
    noteRow.style.cssText='padding:0 14px 10px;position:relative;z-index:2;display:flex;align-items:center;gap:6px';
    const noteCount=(myClassesMap[classId(c)]?.notes||[]).length;
    noteRow.innerHTML=`<button style="display:flex;align-items:center;gap:5px;padding:6px 12px;border-radius:9px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);font-size:12px;color:rgba(236,234,230,.75);cursor:pointer;-webkit-tap-highlight-color:transparent"><i class="ph ph-note-pencil"></i> Notes${noteCount?' ('+noteCount+')':''}</button>`;
    noteRow.querySelector('button').addEventListener('click',e=>{
      e.preventDefault();e.stopPropagation();
      _notesClass=c;renderMyClasses();
    });
    card.appendChild(noteRow);
    listEl.appendChild(card);
  });
}

// ── fav teachers ──
let favTeachers=new Set(JSON.parse(localStorage.getItem('nyd_fav_t')||'[]'));
function toggleFavTeacher(name){
  if(favTeachers.has(name))favTeachers.delete(name);else favTeachers.add(name);
  localStorage.setItem('nyd_fav_t',JSON.stringify([...favTeachers]));
  sbSyncFavTeachers();
}

// ── filter persistence helpers ──
function _serializeFilters(){
  return{studios:[...S.studios],genres:[...S.genres],level:[...S.level],teacher:S.teacher,timeMin:S.timeMin,timeMax:S.timeMax};
}
function _applySerializedFilters(f){
  if(f.studios)S.studios=new Set(f.studios);
  if(f.genres)S.genres=new Set(f.genres);
  if(f.level)S.level=new Set(f.level);
  if(f.teacher!==undefined)S.teacher=f.teacher;
  if(f.timeMin!==undefined)S.timeMin=f.timeMin;
  if(f.timeMax!==undefined)S.timeMax=f.timeMax;
}
function saveFilters(){
  const s=JSON.stringify(_serializeFilters());
  localStorage.setItem('nyd_filters',s);
  sbSyncFilters();
}
// load from localStorage on init (Supabase may overwrite later)
(function(){
  try{
    const raw=localStorage.getItem('nyd_filters');
    if(raw)_applySerializedFilters(JSON.parse(raw));
  }catch(e){}
})();

// ── state ──
// studios: Set — 'all' means no filter; genres: Set of selected genre keys (multi-select)
const S={selectedDate:'',studios:new Set(['all']),
  genres:new Set(['street','contemporary','afro','choreo','conditioning','other']),
  level:new Set(['All Levels','Intermediate','Int/Adv']),
  teacher:'all',timeMin:12,timeMax:24,tab:'schedule'};
// apply persisted filters on top of defaults
(function(){try{const raw=localStorage.getItem('nyd_filters');if(raw)_applySerializedFilters(JSON.parse(raw));}catch(e){}})();

// ── genre → card style ──
const GENRE_STYLES={
  street:      ['card-street-0','card-street-1','card-street-2'],
  ballet:      ['card-ballet-0','card-ballet-1','card-ballet-2'],
  contemporary:['card-contemp-0','card-contemp-1','card-contemp-2'],
  afro:        ['card-afro-0','card-afro-1','card-afro-2'],
  latin:       ['card-latin-0','card-latin-1','card-latin-2'],
  heels:       ['card-heels-0','card-heels-1','card-heels-2'],
  choreo:      ['card-choreo-0','card-choreo-1','card-choreo-2'],
  conditioning:['card-other-0','card-other-1','card-other-2'],
  tap:         ['card-other-0','card-other-1','card-other-2'],
  other:       ['card-other-0','card-other-1','card-other-2'],
};
function cardStyle(c){
  if(c.studio_key==='custom') return 'card-custom-popup';
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

function isPastClass(c){
  if(!c.date_key||c.start_hour<0)return false;
  const[y,m,d]=c.date_key.split('-').map(Number);
  const classTime=new Date(y,m-1,d,Math.floor(c.start_hour),Math.round((c.start_hour%1)*60));
  return classTime<new Date();
}

function matchesFilters(c){
  if(!S.studios.has('all')&&!S.studios.has(c.studio_key))return false;
  if(!S.genres.has(c.genre))return false;
  if(!S.level.has('all')&&!S.level.has(c.level))return false;
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

// ── calendar: 7-day strip (today + 6 days) ──
function renderCalendar(){
  const strip=document.getElementById('weekStrip');
  const dotDates=datesWithClasses();
  const today=todayKey();
  const todayDate=new Date();todayDate.setHours(0,0,0,0);

  // Update page title from selected date's month
  if(S.selectedDate){
    const[sy,sm]=S.selectedDate.split('-').map(Number);
    document.getElementById('pageTitle').textContent=MONTHS[sm-1]+' \''+String(sy).slice(-2);
  }

  // Preserve scroll position across re-renders
  const prevScroll=strip.scrollLeft;
  strip.innerHTML='';
  let selectedEl=null,todayEl=null;

  for(let i=0;i<21;i++){
    const d=new Date(todayDate);d.setDate(d.getDate()+i);
    const key=isoKey(d);
    const col=document.createElement('div');
    col.className='day-col'+(key===S.selectedDate?' selected':'')+(key===today?' today':'')+(dotDates.has(key)?' has-classes':'');
    col.innerHTML=`<span class="day-letter">${DAY_LETTERS[d.getDay()]}</span><span class="day-num">${d.getDate()}</span><span class="day-dot"></span>`;
    col.addEventListener('click',()=>{S.selectedDate=key;renderAll()});
    strip.appendChild(col);
    if(key===S.selectedDate)selectedEl=col;
    if(key===today)todayEl=col;
  }

  // On first load start at left (today visible, 7 days shown); otherwise restore scroll
  if(prevScroll===0){
    strip.scrollLeft=0;
    // If selected date is not today, scroll it just into view (don't center)
    if(selectedEl&&S.selectedDate!==today){
      requestAnimationFrame(()=>selectedEl.scrollIntoView({behavior:'instant',inline:'nearest'}));
    }
  } else {
    strip.scrollLeft=prevScroll;
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

// ── wishlist tab ──
function renderSaved(){
  document.getElementById('pageTitle').textContent='Wishlist';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  const listEl=document.getElementById('classesList');
  const savedFromSchedule=ALL_CLASSES.filter(c=>isSaved(c));
  const allSaved=[...savedFromSchedule,...CUSTOM_CLASSES];
  if(!allSaved.length){
    listEl.innerHTML=`<div class="empty-state"><div class="empty-icon">🔖</div><div class="empty-title">No saved classes yet</div><div class="empty-sub">Tap the bookmark on any card to save it here.</div></div>`;
    return;
  }
  allSaved.sort((a,b)=>a.date_key<b.date_key?-1:a.date_key>b.date_key?1:a.start_hour-b.start_hour);
  listEl.innerHTML='';let lastDate='';
  allSaved.forEach((c,i)=>{
    if(c.date_key!==lastDate){
      const div=document.createElement('div');div.className='section-divider date-divider';
      div.innerHTML=`${formatDateFull(c.date_key)}<div class="section-line"></div>`;
      listEl.appendChild(div);lastDate=c.date_key;
    }
    listEl.appendChild(buildCard(c,i));
  });
}

// ── card builder ──
// ── stamp watermark ──
const STAMP_IMG_URL='__WATERMARK_URL__';

function _stampParams(id){
  // Deterministic seed from classId so stamp looks the same on re-render
  let h=0;for(const ch of id)h=(h*31+ch.charCodeAt(0))>>>0;
  const rot=((h%29)-14).toFixed(1)+'deg';           // -14° to +14°
  const sc=(0.82+(h>>8&0xFF)/255*0.33).toFixed(2);  // 0.82–1.15
  const op=(0.30+(h>>16&0xFF)/255*0.26).toFixed(2); // 0.30–0.56
  return{rot,sc,op};
}
function _attachStamp(div,c,animate){
  const p=_stampParams(classId(c));
  const el=document.createElement('div');
  el.className='stamp-mark'+(animate?' stamp-enter':' stamp-show');
  el.style.cssText=`--sr:${p.rot};--ss:${p.sc};--so:${p.op}`;
  const img=document.createElement('img');
  img.src=STAMP_IMG_URL;
  el.appendChild(img);
  div.appendChild(el);
  return el;
}

function buildCard(c,i){
  const div=document.createElement('div');
  div.className=`card ${cardStyle(c)}${c.is_canceled?' card-canceled':''}${isPastClass(c)?' card-past':''}`;
  div.style.animationDelay=`${Math.min(i*35,200)}ms`;

  const color=avatarColor(c.instructor);
  const abbr=initials(c.instructor);
  const timeStr=c.start_display?(c.end_display?`${c.start_display} – ${c.end_display}`:c.start_display):'';
  const dayAbbr=c.date_key?(()=>{const[y,mo,d]=c.date_key.split('-').map(Number);return DAY_LETTERS[new Date(y,mo-1,d).getDay()]})():'';
  const metaStr=c.studio+(dayAbbr?' · '+dayAbbr:'')+(timeStr?' · '+timeStr:'');
  const saved=isSaved(c);
  const stamped=isMyClass(c);
  const customTag=c.is_custom?'<span class="custom-tag">✦ CUSTOM</span>':'';

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
      <div class="card-header-row">
        <div class="card-meta">${customTag}${esc(metaStr)}</div>
        <div class="card-actions">
          <button class="my-btn${stamped?' stamped':''}" aria-label="${stamped?'Unmark':'Mark as attended'}">
            <i class="${stamped?'ph-fill':'ph'} ph-stamp"></i>
          </button>
          <button class="save-btn${saved?' saved':''}" aria-label="${saved?'Unsave':'Save'}">
            <i class="${saved?'ph-fill':'ph'} ph-shooting-star"></i>
          </button>
        </div>
      </div>
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
    btn.querySelector('i').className=(nowSaved?'ph-fill':'ph')+' ph-shooting-star';
    if(S.tab==='saved')setTimeout(renderSaved,60);
  });
  // Render stamp mark if already stamped (no animation on re-render)
  if(stamped)_attachStamp(div,c,false);

  div.querySelector('.my-btn').addEventListener('click',e=>{
    e.preventDefault();e.stopPropagation();
    const nowStamped=toggleMyClass(c);
    const btn=e.currentTarget;
    btn.classList.toggle('stamped',nowStamped);
    btn.setAttribute('aria-label',nowStamped?'Unmark':'Mark as attended');
    btn.querySelector('i').className=(nowStamped?'ph-fill':'ph')+' ph-stamp';
    // Add or remove stamp watermark
    const existing=div.querySelector('.stamp-mark');
    if(nowStamped){if(!existing)_attachStamp(div,c,true);}
    else{if(existing)existing.remove();}
    if(S.tab==='myclasses')setTimeout(renderMyClasses,60);
  });
  return div;
}

// ── sync chip UI from S state (used after loading persisted filters) ──
function syncChipsFromState(){
  // studio chips
  document.querySelectorAll('#studioChipRow .fchip').forEach(c=>{
    const v=c.dataset.studio;
    c.classList.toggle('active',v==='all'?S.studios.has('all'):S.studios.has(v));
  });
  // genre chips
  document.querySelectorAll('#genreChipRow .fchip').forEach(c=>{
    c.classList.toggle('active',S.genres.has(c.dataset.genre));
  });
  // level chips
  document.querySelectorAll('#levelChipRow .fchip').forEach(c=>{
    const v=c.dataset.level;
    c.classList.toggle('active',v==='all'?S.level.has('all'):S.level.has(v));
  });
  // sliders
  const rMin=document.getElementById('rangeMin');
  const rMax=document.getElementById('rangeMax');
  if(rMin)rMin.value=S.timeMin;
  if(rMax)rMax.value=S.timeMax;
  updateSlider();
}

// ── drawer ──
function openDrawer(){
  document.getElementById('drawerOverlay').classList.add('open');
  document.getElementById('drawer').classList.add('open');
  document.body.style.overflow='hidden';
  syncChipsFromState();buildTeacherChips();updateApplyBtn();
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

// ── genre chips (multi-select, no All) ──
function initGenreChips(){
  document.querySelectorAll('#genreChipRow .fchip').forEach(chip=>{
    chip.addEventListener('click',()=>{
      chip.classList.toggle('active');
      const val=chip.dataset.genre;
      if(chip.classList.contains('active')) S.genres.add(val);
      else S.genres.delete(val);
      buildTeacherChips();updateApplyBtn();
    });
  });
}

// ── level chips (multi-select) ──
function initLevelChips(){
  document.querySelectorAll('#levelChipRow .fchip').forEach(chip=>{
    chip.addEventListener('click',()=>{
      const val=chip.dataset.level;
      if(val==='all'){
        S.level=new Set(['all']);
        document.querySelectorAll('#levelChipRow .fchip').forEach(c=>
          c.classList.toggle('active',c.dataset.level==='all'));
      } else {
        S.level.delete('all');
        chip.classList.toggle('active');
        if(chip.classList.contains('active'))S.level.add(val);
        else S.level.delete(val);
        if(S.level.size===0)S.level.add('all');
        document.querySelector('#levelChipRow .fchip[data-level="all"]')
          .classList.toggle('active',S.level.has('all'));
      }
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
      .filter(c=>c.instructor&&!c.instructor.includes('LLC')&&c.instructor!=='Various *'&&c.instructor!=='Modega'&&c.instructor!=='Modega Staff')
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

// ── nav capsule ──
let _navCurrent='schedule',_navBusy=false;
function _navTabEl(tab){const m={schedule:'navSchedule',popup:'navPopup',wishlist:'navWishlist',myclasses:'navMyclasses'};return document.getElementById(m[tab])}

function snapCapsule(tabEl){
  const capsule=document.getElementById('navCapsule');
  capsule.style.transition='none';
  capsule.getBoundingClientRect();
  capsule.style.left=tabEl.offsetLeft+'px';
  capsule.style.width=tabEl.offsetWidth+'px';
  requestAnimationFrame(()=>{capsule.style.transition=''});
}
function slideCapsule(tabEl){
  const capsule=document.getElementById('navCapsule');
  capsule.style.left=tabEl.offsetLeft+'px';
  capsule.style.width=tabEl.offsetWidth+'px';
  // Re-sync after tab fully expands (label CSS transition = 380ms)
  setTimeout(()=>{
    capsule.style.transition='none';
    capsule.style.left=tabEl.offsetLeft+'px';
    capsule.style.width=tabEl.offsetWidth+'px';
    requestAnimationFrame(()=>{capsule.style.transition=''});
  },420);
}

// ── tab switching ──
function switchTab(tab){
  if(tab==='popup'){
    if(_navCurrent==='popup')return;
    _animateNav('popup',()=>{ renderPopup(); });
    S.tab='popup';
    return;
  }
  if(tab===_navCurrent)return;
  if(tab==='schedule'){
    _animateNav('schedule',()=>{
      document.getElementById('weekStrip').style.display='';
      document.getElementById('updatedText').style.visibility='visible';
      renderAll();
    });
    S.tab='schedule';
  } else if(tab==='wishlist'){
    _animateNav('wishlist',()=>{renderSaved()});
    S.tab='saved';
  } else {
    _animateNav('myclasses',()=>{renderMyClasses()});
    S.tab='myclasses';
  }
}

function _animateNav(newTab,callback){
  const oldEl=_navTabEl(_navCurrent);
  const newEl=_navTabEl(newTab);
  // 1. fade out old label
  const oldLbl=oldEl.querySelector('.tab-label');
  oldLbl.style.opacity='0';
  oldLbl.style.transition='opacity 0.1s';
  setTimeout(()=>{
    // 2. swap active classes — keep new label hidden until capsule lands
    oldEl.classList.remove('active');
    newEl.classList.add('active');
    const newLbl=newEl.querySelector('.tab-label');
    newLbl.style.transition='none';
    newLbl.style.opacity='0';
    _navCurrent=newTab;
    // 3. slide capsule (initial measurement — tab not yet fully expanded)
    requestAnimationFrame(()=>{
      slideCapsule(newEl);
      // 4. show new label after capsule settles
      setTimeout(()=>{
        newLbl.style.transition='opacity 0.18s';
        newLbl.style.opacity='1';
        _navBusy=false;
      },350);
    });
    callback();
  },110);
  _navBusy=true;
}

// ── event listeners ──
document.getElementById('rangeMin').addEventListener('input',updateSlider);
document.getElementById('rangeMax').addEventListener('input',updateSlider);
document.getElementById('filterBtn').addEventListener('click',openDrawer);
document.getElementById('drawerClose').addEventListener('click',closeDrawer);
document.getElementById('drawerOverlay').addEventListener('click',closeDrawer);
document.getElementById('applyBtn').addEventListener('click',()=>{saveFilters();closeDrawer();renderAll()});
document.getElementById('teacherSearch').addEventListener('input',buildTeacherChips);
['navSchedule','navPopup','navWishlist','navMyclasses'].forEach(id=>{
  document.getElementById(id).addEventListener('click',()=>{
    if(_navBusy)return;
    const tab=id==='navSchedule'?'schedule':id==='navPopup'?'popup':id==='navWishlist'?'wishlist':'myclasses';
    switchTab(tab);
  });
});

function renderAll(){renderCalendar();renderClasses()}

// ── swipe to change day with slide animation (schedule tab only) ──
(function(){
  let _tx=0,_ty=0,_busy=false;
  const scroller=document.getElementById('mainScroll');
  const _dates=()=>{const t=new Date();t.setHours(0,0,0,0);const a=[];for(let i=0;i<21;i++){const d=new Date(t);d.setDate(d.getDate()+i);a.push(isoKey(d));}return a;};

  scroller.addEventListener('touchstart',e=>{
    _tx=e.touches[0].clientX;_ty=e.touches[0].clientY;
  },{passive:true});

  scroller.addEventListener('touchend',e=>{
    if(S.tab!=='schedule'||_busy)return;
    const dx=e.changedTouches[0].clientX-_tx;
    const dy=e.changedTouches[0].clientY-_ty;
    if(Math.abs(dx)<44||Math.abs(dx)<Math.abs(dy)*1.5)return;

    const dates=_dates();
    const idx=dates.indexOf(S.selectedDate);
    let nextDate=null;
    const dir=dx<0?-1:1; // -1=left swipe (next day), +1=right swipe (prev day)
    if(dir===-1&&idx<dates.length-1)nextDate=dates[idx+1];
    else if(dir===1&&idx>0)nextDate=dates[idx-1];
    if(!nextDate)return;

    _busy=true;
    const list=document.getElementById('classesList');
    // swipe left (dir=-1): list exits LEFT (-28%), new enters from RIGHT (+28%)
    const OUT_X=dir*28;   // -1 → -28% (left), +1 → +28% (right)
    const IN_X=dir*-28;   // -1 → +28% (from right), +1 → -28% (from left)

    // 1. Slide out + fade
    list.style.transition='transform 0.17s ease-in,opacity 0.17s ease-in';
    list.style.transform=`translateX(${OUT_X}%)`;
    list.style.opacity='0';

    setTimeout(()=>{
      // 2. Update state & render
      S.selectedDate=nextDate;
      renderAll();
      // 3. Instantly position new content off-screen on opposite side
      list.style.transition='none';
      list.style.transform=`translateX(${IN_X}%)`;
      list.style.opacity='0';
      // 4. Slide in
      requestAnimationFrame(()=>requestAnimationFrame(()=>{
        list.style.transition='transform 0.24s cubic-bezier(.25,.46,.45,.94),opacity 0.2s ease-out';
        list.style.transform='translateX(0)';
        list.style.opacity='1';
        setTimeout(()=>_busy=false,260);
      }));
    },190);
  },{passive:true});
})();

// ── init ──
(function init(){
  initStudioChips();initGenreChips();initLevelChips();
  const today=todayKey();
  const allDates=[...new Set(ALL_CLASSES.filter(c=>!c.is_canceled).map(c=>c.date_key))].sort();
  const future=allDates.filter(d=>d>=today);
  S.selectedDate=future.length?future[0]:allDates[allDates.length-1];
  syncChipsFromState();buildTeacherChips();renderAll();
  // Init nav capsule after Phosphor icons are rendered (use window.onload)
  const _initCapsule=()=>{
    const initEl=document.getElementById('navSchedule');
    const initLbl=initEl.querySelector('.tab-label');
    initLbl.style.transition='none';
    initLbl.style.opacity='1';
    snapCapsule(initEl);
    requestAnimationFrame(()=>{ initLbl.style.transition=''; });
  };
  if(document.readyState==='complete') _initCapsule();
  else window.addEventListener('load',_initCapsule);
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
    html = html.replace("__WATERMARK_URL__", _watermark_data_url())

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
