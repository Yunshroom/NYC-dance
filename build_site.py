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
        return "Adv Beg"
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
            level_override=extract_level(name) or c.get("level"),
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

/* Contemporary — deep teal */
.card-contemp-0{background:linear-gradient(155deg,#082428 0%,#020c10 72%);background-image:repeating-linear-gradient(60deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#082428 0%,#020c10 72%)}
.card-contemp-1{background:linear-gradient(155deg,#061e24 0%,#020a0e 72%);background-image:repeating-linear-gradient(140deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#061e24 0%,#020a0e 72%)}
.card-contemp-2{background:linear-gradient(155deg,#0a2020 0%,#040e0e 72%);background-image:repeating-linear-gradient(30deg,rgba(255,255,255,.048) 0,rgba(255,255,255,.048) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#0a2020 0%,#040e0e 72%)}

/* Afro — amber/gold family */
.card-afro-0{background:linear-gradient(155deg,#2e1a06 0%,#160800 72%);background-image:repeating-linear-gradient(50deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#2e1a06 0%,#160800 72%)}
.card-afro-1{background:linear-gradient(155deg,#321c08 0%,#180a00 72%);background-image:repeating-linear-gradient(115deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#321c08 0%,#180a00 72%)}
.card-afro-2{background:linear-gradient(155deg,#281808 0%,#120600 72%);background-image:repeating-linear-gradient(22deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#281808 0%,#120600 72%)}

/* Latin — dark cool grey */
.card-latin-0{background:linear-gradient(155deg,#1e1c22 0%,#0e0c10 72%);background-image:repeating-linear-gradient(70deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#1e1c22 0%,#0e0c10 72%)}
.card-latin-1{background:linear-gradient(155deg,#1c1a20 0%,#0c0a0e 72%);background-image:repeating-linear-gradient(145deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#1c1a20 0%,#0c0a0e 72%)}
.card-latin-2{background:linear-gradient(155deg,#201e24 0%,#100e12 72%);background-image:repeating-linear-gradient(28deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#201e24 0%,#100e12 72%)}

/* Heels — dark cool grey */
.card-heels-0{background:linear-gradient(155deg,#1c1c1e 0%,#0c0c0e 72%);background-image:repeating-linear-gradient(65deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#1c1c1e 0%,#0c0c0e 72%)}
.card-heels-1{background:linear-gradient(155deg,#1a1a1c 0%,#0a0a0c 72%);background-image:repeating-linear-gradient(130deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#1a1a1c 0%,#0a0a0c 72%)}
.card-heels-2{background:linear-gradient(155deg,#1e1e20 0%,#0e0e10 72%);background-image:repeating-linear-gradient(15deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#1e1e20 0%,#0e0e10 72%)}

/* Other / Conditioning / Tap — warm neutral */
.card-other-0{background:linear-gradient(155deg,#201c14 0%,#0e0c06 72%);background-image:repeating-linear-gradient(80deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#201c14 0%,#0e0c06 72%)}
.card-other-1{background:linear-gradient(155deg,#1e1a14 0%,#0c0a08 72%);background-image:repeating-linear-gradient(155deg,rgba(255,255,255,.045) 0,rgba(255,255,255,.045) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#1e1a14 0%,#0c0a08 72%)}
.card-other-2{background:linear-gradient(155deg,#221c10 0%,#100c04 72%);background-image:repeating-linear-gradient(35deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#221c10 0%,#100c04 72%)}

/* Choreo — dark rose/mauve */
.card-choreo-0{background:linear-gradient(155deg,#30101e 0%,#160608 72%);background-image:repeating-linear-gradient(75deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 7px),linear-gradient(155deg,#30101e 0%,#160608 72%)}
.card-choreo-1{background:linear-gradient(155deg,#2c0e24 0%,#140610 72%);background-image:repeating-linear-gradient(145deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#2c0e24 0%,#140610 72%)}
.card-choreo-2{background:linear-gradient(155deg,#34141e 0%,#180808 72%);background-image:repeating-linear-gradient(28deg,rgba(255,255,255,.05) 0,rgba(255,255,255,.05) 1px,transparent 1px,transparent 9px),linear-gradient(155deg,#34141e 0%,#180808 72%)}

.card-canceled{opacity:.48}
/* Past class on schedule tab — flat grey, no stripe pattern, muted text */
.card-past{background:#1d1b19 !important;background-image:none !important}
.card-past .card-meta{color:rgba(160,155,145,.45) !important}
.card-past .card-name{color:rgba(190,185,175,.5) !important}
.card-past .card-instructor-name{color:rgba(160,155,145,.4) !important}
.card-past .small-avatar{opacity:.3}
.card-past .card-tap{pointer-events:none}
/* card-inner has no z-index so save-btn can rise above card-tap in card's stacking context */
.card-inner{padding:14px;position:relative}
.card-tap{position:absolute;inset:0;z-index:1}
.card-header-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:7px}
.card-actions{display:flex;align-items:center;gap:0;position:relative;z-index:2;flex-shrink:0}
.save-btn,.my-btn{color:rgba(232,228,220,.4);line-height:1;padding:10px 8px;transition:color .2s;background:none;border:none;cursor:pointer;-webkit-tap-highlight-color:transparent;margin:-8px 0}
.save-btn i,.my-btn i{font-size:20px;transition:color .2s;display:block}
.save-btn.saved{color:#d4537e}
.save-btn.saved i{color:#d4537e}
.my-btn.stamped{color:#f0a830}
.my-btn.stamped i{color:#f0a830}
/* inline notes */
.inline-notes-wrap{padding:0 14px 14px;position:relative;z-index:2}
.inline-notes-toggle{display:flex;align-items:center;gap:6px;width:100%;padding:7px 10px;border-radius:8px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);color:rgba(236,234,230,.65);font-family:'DM Mono',monospace;font-size:11px;cursor:pointer;-webkit-tap-highlight-color:transparent;text-align:left}
.inline-notes-toggle i{font-size:13px}
.inline-notes-caret{margin-left:auto}
.inline-notes-panel{padding:10px 0 0;position:relative}
.mc-dots-btn{color:rgba(232,228,220,.4);line-height:1;padding:2px 6px;background:none;border:none;cursor:pointer;-webkit-tap-highlight-color:transparent}
.mc-dots-btn i{font-size:20px}
.mc-dots-menu{background:#2a2724;border:1px solid rgba(255,255,255,.12);border-radius:10px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,.5);min-width:190px}
.mc-dots-item{display:flex;align-items:center;gap:8px;width:100%;padding:12px 16px;background:none;border:none;color:rgba(236,234,230,.85);font-size:14px;cursor:pointer;text-align:left;-webkit-tap-highlight-color:transparent}
.mc-dots-item:active{background:rgba(255,255,255,.07)}
.mc-dots-delete{color:#e06070 !important}
/* Scrapbook notes */
.sticky-note{border-radius:4px;padding:11px 13px;position:relative;border-bottom:2px solid rgba(0,0,0,.07);transition:transform .2s}
.sticky-tape{position:absolute;top:-7px;left:50%;transform:translateX(-50%);width:30px;height:11px;border-radius:2px;opacity:.5}
@keyframes noteIn{from{opacity:0;transform:scale(.88) rotate(var(--r,0deg))}to{opacity:1;transform:scale(1) rotate(var(--r,0deg))}}
.note-in{animation:noteIn .32s cubic-bezier(.34,1.4,.5,1) both}
@keyframes recPulse{0%,100%{opacity:1}50%{opacity:.4}}
.rec-pulse{animation:recPulse 1.2s ease-in-out infinite}
.note-pill-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;border-radius:999px;padding:9px 14px;cursor:pointer;font-family:'DM Mono',monospace;font-size:11px;-webkit-tap-highlight-color:transparent;transition:background .18s,opacity .15s;background:rgba(255,255,255,.08);backdrop-filter:blur(14px) saturate(1.6);-webkit-backdrop-filter:blur(14px) saturate(1.6);border:.5px solid rgba(255,255,255,.14);color:rgba(232,228,220,.82);box-shadow:0 2px 8px rgba(0,0,0,.18),0 .5px 0 rgba(255,255,255,.08) inset}
.note-pill-btn:active{background:rgba(255,255,255,.14);opacity:.85}
.notes-hidden .inline-notes-wrap{display:none!important}
.notes-hide-toggle{display:flex;align-items:center;gap:5px;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);color:rgba(220,216,208,.6);font-family:'DM Mono',monospace;font-size:10px;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:background .15s,color .15s;white-space:nowrap}
.notes-hide-toggle.active{background:rgba(127,119,221,.2);border-color:rgba(127,119,221,.4);color:rgba(200,196,255,.9)}
.notes-hide-toggle i{font-size:13px}

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

/* ── glassmorphic pill nav — readable on both light & dark backgrounds ── */
#bottomNav{position:absolute;bottom:0;left:0;right:0;display:flex;justify-content:center;padding:12px 20px calc(12px + env(safe-area-inset-bottom));z-index:50;pointer-events:none}
.nav-bar{position:relative;display:inline-flex;align-items:center;gap:2px;background:rgba(22,18,14,.72);backdrop-filter:blur(32px) saturate(2);-webkit-backdrop-filter:blur(32px) saturate(2);border:.5px solid rgba(255,255,255,.18);border-radius:50px;padding:5px;box-shadow:0 4px 6px rgba(0,0,0,.12),0 12px 36px rgba(0,0,0,.38),0 1px 0 rgba(255,255,255,.1) inset;pointer-events:all}
.nav-capsule{position:absolute;border-radius:40px;background:rgba(62,54,44,.72);border:.5px solid rgba(255,255,255,.22);box-shadow:0 2px 10px rgba(0,0,0,.35),0 .5px 0 rgba(255,255,255,.1) inset;top:5px;bottom:5px;left:5px;pointer-events:none;transition:left .38s cubic-bezier(.34,1.4,.64,1),width .38s cubic-bezier(.34,1.4,.64,1)}
.nav-tab{position:relative;z-index:1;display:flex;align-items:center;gap:0;padding:9px 12px;border-radius:40px;background:none;border:none;cursor:pointer;-webkit-tap-highlight-color:transparent}
.tab-icon i{font-size:21px;color:rgba(200,194,184,.7);display:block;flex-shrink:0;transition:color .2s}
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
/* ── saved tab section headers ── */
.saved-section-header{font-size:11px;font-weight:600;color:#6b6860;text-transform:uppercase;letter-spacing:.08em;display:flex;align-items:center;gap:6px;padding:4px 0 2px;margin-bottom:4px}
.saved-section-header i{font-size:14px;color:#6b6860}
/* ── popup add FAB ── */
.popup-add-fab{display:inline-flex;align-items:center;gap:8px;padding:11px 18px;border-radius:12px;background:linear-gradient(155deg,#1e1a16 0%,#0e0a08 72%);background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.04) 0,rgba(255,255,255,.04) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#1e1a16 0%,#0e0a08 72%);border:none;color:#f5f1ea;font-family:'DM Mono',monospace;font-size:11px;font-weight:500;letter-spacing:.07em;text-transform:uppercase;cursor:pointer;-webkit-tap-highlight-color:transparent;margin-bottom:6px}
.popup-add-fab i{font-size:17px}
.popup-add-fab:active{opacity:.8}
.popup-add-options{display:flex;gap:8px;margin-bottom:12px;animation:fadeSlideDown .18s ease}
@keyframes fadeSlideDown{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.popup-add-opt{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;padding:13px 8px;border-radius:13px;background:#f0ece6;border:none;color:#3a3830;font-size:11px;font-family:'DM Mono',monospace;letter-spacing:.04em;cursor:pointer;position:relative;-webkit-tap-highlight-color:transparent}
.popup-add-opt i{font-size:22px;color:#3a3830}
.popup-add-opt:active{background:#e4e0da}
/* ── profile tab ── */
.profile-pane{padding:4px 0 80px}
.profile-hero{border-radius:14px;overflow:hidden;margin-bottom:10px;padding:20px 18px 22px;background:linear-gradient(155deg,#1e1a16 0%,#0e0a08 72%);background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.04) 0,rgba(255,255,255,.04) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#1e1a16 0%,#0e0a08 72%);position:relative}
.profile-hero-label{font-family:'DM Mono',monospace;font-size:10px;color:rgba(200,195,185,.45);text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
.profile-hero-num{font-family:'Permanent Marker',cursive;font-size:64px;color:#f5f1ea;line-height:1;margin-bottom:2px}
.profile-hero-sub{font-family:'DM Mono',monospace;font-size:11px;color:rgba(200,195,185,.5);letter-spacing:.04em}
.profile-email-row{font-family:'DM Mono',monospace;font-size:11px;color:rgba(200,195,185,.38);letter-spacing:.04em;margin-bottom:14px}
.profile-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.stat-card{border-radius:14px;overflow:hidden;padding:16px 14px;background:linear-gradient(155deg,#1e1a16 0%,#0e0a08 72%);background-image:repeating-linear-gradient(60deg,rgba(255,255,255,.04) 0,rgba(255,255,255,.04) 1px,transparent 1px,transparent 8px),linear-gradient(155deg,#1e1a16 0%,#0e0a08 72%);display:flex;flex-direction:column;gap:3px}
.stat-card.full{grid-column:1/-1}
.stat-num{font-family:'DM Mono',monospace;font-size:30px;font-weight:500;color:#f5f1ea;line-height:1;letter-spacing:-1px}
.stat-label{font-family:'DM Mono',monospace;font-size:10px;color:rgba(200,195,185,.4);text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
.stat-sub{font-family:'DM Mono',monospace;font-size:10px;color:rgba(200,195,185,.45);margin-top:4px;letter-spacing:.02em}
.stat-name{font-family:'DM Sans',sans-serif;font-size:17px;font-weight:500;color:#f5f1ea;margin-top:5px;line-height:1.2}
.genre-bars{display:flex;flex-direction:column;gap:9px;margin-top:10px}
.genre-bar-row{display:flex;align-items:center;gap:8px}
.genre-bar-label{font-family:'DM Mono',monospace;font-size:10px;color:rgba(200,195,185,.55);width:66px;flex-shrink:0;text-transform:capitalize;letter-spacing:.02em}
.genre-bar-track{flex:1;height:4px;background:rgba(255,255,255,.1);border-radius:4px;overflow:hidden}
.genre-bar-fill{height:100%;border-radius:4px;background:rgba(200,195,185,.5)}
.genre-bar-count{font-family:'DM Mono',monospace;font-size:10px;color:rgba(200,195,185,.4);width:18px;text-align:right;flex-shrink:0}

/* custom card badge */
.custom-tag{font-size:9px;font-weight:700;letter-spacing:.08em;color:rgba(255,210,80,.95);text-transform:uppercase;background:rgba(255,210,80,.14);border-radius:3px;padding:1px 5px;margin-right:5px;flex-shrink:0;vertical-align:middle}
/* stamp watermark — pinned to top-right, doesn't move when card grows */
.stamp-mark{position:absolute;right:10px;top:10px;pointer-events:none;transform-origin:center center;width:132px;height:132px;}
.stamp-mark img{width:100%;height:100%;display:block;mix-blend-mode:multiply;}
@keyframes stampPress{
  0%  {transform:rotate(var(--sr)) scale(calc(var(--ss)*1.35));opacity:0}
  30% {transform:rotate(var(--sr)) scale(calc(var(--ss)*0.9));opacity:calc(var(--so)*1.5)}
  60% {transform:rotate(var(--sr)) scale(calc(var(--ss)*1.04));opacity:var(--so)}
  100%{transform:rotate(var(--sr)) scale(var(--ss));opacity:var(--so)}
}
.stamp-mark.stamp-enter{animation:stampPress .42s cubic-bezier(.22,.68,0,1.2) both}
.stamp-mark.stamp-show{transform:rotate(var(--sr)) scale(var(--ss));opacity:var(--so)}
/* ── Login screen ── */
#loginScreen{position:fixed;inset:0;z-index:2000;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(160deg,#1c100e 0%,#0e0a08 100%);padding:32px 24px;text-align:center;transition:opacity .3s}
#loginScreen.hidden{opacity:0;pointer-events:none}
.login-logo{font-size:42px;margin-bottom:10px}
.login-title{font-family:'DM Sans',sans-serif;font-size:28px;font-weight:600;color:#f5f1ea;margin:0 0 4px}
.login-sub{font-family:'DM Mono',monospace;font-size:10px;color:rgba(200,195,185,.45);letter-spacing:.1em;text-transform:uppercase;margin:0 0 36px}
.login-card{width:100%;max-width:320px;background:rgba(255,255,255,.05);border:.5px solid rgba(255,255,255,.12);border-radius:20px;padding:24px;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
.login-input{width:100%;background:rgba(255,255,255,.07);border:.5px solid rgba(255,255,255,.15);border-radius:10px;padding:12px 14px;font-family:'DM Sans',sans-serif;font-size:15px;color:#f5f1ea;outline:none;box-sizing:border-box;margin-bottom:12px;-webkit-appearance:none}
.login-input::placeholder{color:rgba(200,195,185,.35)}
.login-input:focus{border-color:rgba(255,255,255,.3);background:rgba(255,255,255,.1)}
.login-btn{width:100%;padding:13px;border:none;border-radius:10px;background:#f5f1ea;color:#1a1a18;font-family:'DM Mono',monospace;font-size:12px;font-weight:500;letter-spacing:.08em;cursor:pointer;transition:opacity .15s}
.login-btn:active{opacity:.75}
.login-btn:disabled{opacity:.45;cursor:default}
.login-sent{display:none;text-align:center;padding:4px 0}
.login-sent-icon{font-size:32px;margin-bottom:10px}
.login-sent p{font-family:'DM Mono',monospace;font-size:11px;color:rgba(200,195,185,.65);line-height:1.7;margin:0}
.login-hint{font-family:'DM Mono',monospace;font-size:10px;color:rgba(200,195,185,.28);margin-top:14px;letter-spacing:.04em}
.login-error{font-family:'DM Mono',monospace;font-size:11px;color:#e06070;margin-top:10px;display:none}
/* sign-out in header */
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
          <button class="notes-hide-toggle" id="notesToggleBtn" title="Toggle notes" style="display:none">
            <i class="ph ph-note-pencil"></i><span>Notes</span>
          </button>
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
      <button class="nav-tab" data-tab="wishlist" id="navWishlist">
        <span class="tab-icon"><i class="ph ph-shooting-star"></i></span>
        <span class="tab-label">Wishlist</span>
      </button>
      <button class="nav-tab" data-tab="myclasses" id="navMyclasses">
        <span class="tab-icon"><i class="ph ph-stamp"></i></span>
        <span class="tab-label">My Classes</span>
      </button>
      <button class="nav-tab" data-tab="profile" id="navProfile">
        <span class="tab-icon"><i class="ph ph-user-circle"></i></span>
        <span class="tab-label">Profile</span>
      </button>
    </div>
  </nav>
</div>

<!-- ── Login screen (shown until authenticated) ── -->
<div id="loginScreen">
  <div class="login-logo">🎟</div>
  <h1 class="login-title">NYC Dance</h1>
  <p class="login-sub">New York City · 2026</p>
  <div class="login-card">
    <div id="loginForm">
      <input class="login-input" id="loginName" type="text" placeholder="your name" autocomplete="name" autocapitalize="words"/>
      <input class="login-input" id="loginEmail" type="email" placeholder="your@email.com" autocomplete="email" inputmode="email"/>
      <button class="login-btn" id="loginBtn">SEND MAGIC LINK →</button>
      <p class="login-error" id="loginError"></p>
    </div>
    <div class="login-sent" id="loginSent">
      <div class="login-sent-icon">📬</div>
      <p>Check your inbox<br><strong id="loginSentEmail" style="color:rgba(232,228,220,.9)"></strong></p>
    </div>
    <p class="login-hint">no password needed · link expires in 1 hour</p>
  </div>
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
        <button class="fchip active" data-level="Adv Beg">Adv Beg</button>
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
  if(/adv\.?\s*beg|beg\.?\/adv/.test(n))return'Adv Beg';
  if(/absolute.?beginner|beginner|\bbeg\b/.test(n))return'Beginner';
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
  sbSyncCustomClasses();
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
  const LEVEL_LABELS=['All Levels','Beginner','Adv Beg','Intermediate','Int/Adv','Advanced'];

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
    sbSyncCustomClasses();
    const btn=container.querySelector('#pmfSaveBtn');
    btn.textContent='✓ Added!';btn.classList.add('ok');
    setTimeout(()=>{renderSaved();},1200);
  });
}

function renderPopup(){
  _popupParsed=null;
  document.getElementById('pageTitle').textContent='Pop up';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  const _ntB=document.getElementById('notesToggleBtn');if(_ntB)_ntB.style.display='none';
  document.getElementById('filterBtn').style.display='';
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
// ── Supabase + Auth ──────────────────────────────────────────────────────────
// Magic-link auth: user enters email → clicks link → auto logged in.
// Each user gets their own isolated data via auth.uid().
// Legacy data under 'yunshroom-test-01' is migrated on first login.
//
// SQL schema (run in Supabase SQL editor):
// create table if not exists my_classes(user_id text, class_id text, class_json jsonb, added_at timestamptz default now(), primary key(user_id,class_id));
// create table if not exists notes(user_id text, note_id text, class_id text, text text, type text, created_at timestamptz default now(), primary key(user_id,note_id));
// create table if not exists wishlist(user_id text, class_id text, class_json jsonb, saved_at timestamptz default now(), primary key(user_id,class_id));
// create table if not exists custom_classes(user_id text, class_id text, class_json jsonb, created_at timestamptz default now(), primary key(user_id,class_id));
// create table if not exists user_preferences(user_id text, pref_key text, value_json text, updated_at timestamptz default now(), primary key(user_id,pref_key));
//
// RLS (run after first migration is confirmed):
// alter table my_classes enable row level security;
// alter table notes enable row level security;
// alter table wishlist enable row level security;
// alter table custom_classes enable row level security;
// alter table user_preferences enable row level security;
// create policy "own rows" on my_classes using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id);
// create policy "own rows" on notes using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id);
// create policy "own rows" on wishlist using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id);
// create policy "own rows" on custom_classes using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id);
// create policy "own rows" on user_preferences using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id);
const _SB_URL='https://riezaxehqtoaxjysguwe.supabase.co';
const _SB_KEY='sb_publishable_beWZ6S96-qf51IBebC_IVQ_ufUR_E9_';
const _SB_LEGACY_USER='yunshroom-test-01'; // old hardcoded ID — migrated on first login
let _SB_USER=null; // set after authentication
let _sb=null;
let _remoteClassIds=new Set(); // tracks which class_ids exist in Supabase so we can delete removed ones

// ── Login screen helpers ──
let _currentUserEmail='';
let _currentUserName='';
function _hideLoginScreen(label,email){
  const s=document.getElementById('loginScreen');
  if(s){s.classList.add('hidden');setTimeout(()=>{s.style.display='none';},320);}
  if(email)_currentUserEmail=email;
  if(label)_currentUserName=label;
}
function _showLoginScreen(){
  const s=document.getElementById('loginScreen');
  if(s){s.style.display='flex';requestAnimationFrame(()=>s.classList.remove('hidden'));}
}

// ── Legacy data migration (one-time on first login) ──
async function migrateLegacyData(newUserId){
  if(!_sb||!_SB_USER)return;
  console.log('[Auth] migrating legacy data to',newUserId);
  try{
    const[mc,nt,wl,cc,pr]=await Promise.all([
      _sb.from('my_classes').select('*').eq('user_id',_SB_LEGACY_USER),
      _sb.from('notes').select('*').eq('user_id',_SB_LEGACY_USER),
      _sb.from('wishlist').select('*').eq('user_id',_SB_LEGACY_USER),
      _sb.from('custom_classes').select('*').eq('user_id',_SB_LEGACY_USER),
      _sb.from('user_preferences').select('*').eq('user_id',_SB_LEGACY_USER),
    ]);
    const remap=(rows)=>(rows||[]).map(r=>({...r,user_id:newUserId}));
    if(mc.data?.length)await _sb.from('my_classes').upsert(remap(mc.data),{onConflict:'user_id,class_id'});
    if(nt.data?.length)await _sb.from('notes').upsert(remap(nt.data),{onConflict:'user_id,note_id'});
    if(wl.data?.length)await _sb.from('wishlist').upsert(remap(wl.data),{onConflict:'user_id,class_id'});
    if(cc.data?.length)await _sb.from('custom_classes').upsert(remap(cc.data),{onConflict:'user_id,class_id'});
    if(pr.data?.length)await _sb.from('user_preferences').upsert(remap(pr.data),{onConflict:'user_id,pref_key'});
    console.log('[Auth] migration complete');
  }catch(e){console.warn('[Auth] migration error',e);}
}

// ── Supabase client init + auth listener ──
(async function(){
  try{
    if(_SB_URL&&typeof supabase!=='undefined'){
      _sb=supabase.createClient(_SB_URL,_SB_KEY,{auth:{persistSession:true,autoRefreshToken:true}});
      console.log('[Supabase] connected');
      // onAuthStateChange fires immediately with INITIAL_SESSION on every page load
      _sb.auth.onAuthStateChange(async(event,session)=>{
        if(session){
          _SB_USER=session.user.id;
          // Save pending name if set at login time
          const _pendingName=localStorage.getItem('nyd_pending_name');
          if(_pendingName&&!session.user.user_metadata?.display_name){
            await _sb.auth.updateUser({data:{display_name:_pendingName}});
            localStorage.removeItem('nyd_pending_name');
          }
          const displayName=session.user.user_metadata?.display_name||'';
          _hideLoginScreen(displayName||session.user.email, session.user.email);
          sbLoadAll();
        } else if(event==='INITIAL_SESSION'||event==='SIGNED_OUT'){
          _SB_USER=null;
          _showLoginScreen();
        }
      });
    } else {
      console.log('[Supabase] not configured — local-only mode');
      _showLoginScreen();
    }
  }catch(e){console.warn('[Supabase] init error',e);}
})();

async function sbSyncMyClasses(){
  if(!_sb||!_SB_USER)return;
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
  if(!_sb||!_SB_USER)return;
  try{
    const entry=myClassesMap[classId];if(!entry)return;
    const rows=(entry.notes||[]).map(n=>({user_id:_SB_USER,note_id:n.id,class_id:classId,text:n.text,type:n.type,created_at:n.created_at}));
    // delete removed notes then upsert current
    await _sb.from('notes').delete().eq('user_id',_SB_USER).eq('class_id',classId);
    if(rows.length)await _sb.from('notes').upsert(rows,{onConflict:'user_id,note_id'});
  }catch(e){console.warn('[Supabase] sbSyncNotes error',e);}
}
async function sbSyncWishlist(){
  if(!_sb||!_SB_USER)return;
  try{
    const ids=JSON.parse(localStorage.getItem('nyd_saved')||'[]');
    const rows=ids.map(id=>({user_id:_SB_USER,class_id:id,saved_at:new Date().toISOString()}));
    await _sb.from('wishlist').delete().eq('user_id',_SB_USER);
    if(rows.length)await _sb.from('wishlist').upsert(rows,{onConflict:'user_id,class_id'});
  }catch(e){console.warn('[Supabase] sbSyncWishlist error',e);}
}
async function sbSyncCustomClasses(){
  if(!_sb||!_SB_USER)return;
  try{
    const rows=CUSTOM_CLASSES.map(c=>({user_id:_SB_USER,class_id:classId(c),class_json:c,created_at:new Date().toISOString()}));
    await _sb.from('custom_classes').delete().eq('user_id',_SB_USER);
    if(rows.length)await _sb.from('custom_classes').upsert(rows,{onConflict:'user_id,class_id'});
  }catch(e){console.warn('[Supabase] sbSyncCustomClasses error',e);}
}
async function sbSyncFavTeachers(){
  if(!_sb||!_SB_USER)return;
  try{
    const val=JSON.stringify([...favTeachers]);
    await _sb.from('user_preferences').upsert([{user_id:_SB_USER,pref_key:'fav_teachers',value_json:val}],{onConflict:'user_id,pref_key'});
  }catch(e){console.warn('[Supabase] sbSyncFavTeachers error',e);}
}
async function sbSyncFilters(){
  if(!_sb||!_SB_USER)return;
  try{
    const val=JSON.stringify(_serializeFilters());
    await _sb.from('user_preferences').upsert([{user_id:_SB_USER,pref_key:'filters',value_json:val}],{onConflict:'user_id,pref_key'});
  }catch(e){console.warn('[Supabase] sbSyncFilters error',e);}
}
async function sbLoadAll(){
  if(!_sb||!_SB_USER)return;
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
    // ── custom classes: Supabase is source of truth ──
    const{data:cc}=await _sb.from('custom_classes').select('class_json').eq('user_id',_SB_USER);
    if(cc){
      const arr=(cc||[]).map(r=>r.class_json);
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
    // Re-render the currently active tab so remote data shows up correctly
    if(S.tab==='myclasses'&&typeof renderMyClasses==='function')renderMyClasses();
    else if(S.tab==='saved'&&typeof renderSaved==='function')renderSaved();
    else if(S.tab==='profile'&&typeof renderProfile==='function')renderProfile();
    else if(typeof renderAll==='function')renderAll();
  }catch(e){console.warn('[Supabase] sbLoadAll error',e);}
}
// sbLoadAll() is triggered by the auth state listener, not directly on startup

// myClassesMap: {classId → {notes, added_at}}
function isMyClass(c){const e=myClassesMap[classId(c)];return!!(e&&!e._wishlistOnly)}
function toggleMyClass(c){
  const id=classId(c);
  const existing=myClassesMap[id];
  if(existing&&!existing._wishlistOnly){
    // fully stamped → un-stamp; keep entry if it has notes, else delete
    if(existing.notes&&existing.notes.length){existing._wishlistOnly=true;}
    else{delete myClassesMap[id];}
  } else {
    // not stamped (or wishlist-only) → stamp it, preserve any existing notes
    myClassesMap[id]={notes:existing?existing.notes:[],added_at:new Date().toISOString()};
  }
  localStorage.setItem('nyd_my_classes',JSON.stringify(myClassesMap));
  sbSyncMyClasses();
  return isMyClass(c);
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
    const textBtn=document.createElement('button');
    textBtn.className='note-pill-btn';
    textBtn.innerHTML='<i class="ph ph-pencil-simple" style="font-size:14px"></i> text note';
    textBtn.addEventListener('click',_showTextInput);
    row.appendChild(textBtn);
    const voiceBtn=document.createElement('button');
    voiceBtn.className='note-pill-btn';
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

function _buildInlineNotes(c){
  const id=classId(c);
  const wrap=document.createElement('div');
  wrap.className='inline-notes-wrap';

  // ── shared: build a sticky note card ──
  function _buildSticky(n,i,isNew,onDelete){
    const col=stickyColor(i);
    const rot=noteRot(i);
    const dt=new Date(n.created_at);
    const hh=dt.getHours(),mm=dt.getMinutes(),period=hh>=12?'PM':'AM';
    const dh=hh%12||12;
    const timeStr=`${dh}:${String(mm).padStart(2,'0')} ${period}`;
    const card=document.createElement('div');
    card.className='sticky-note'+(isNew?' note-in':'');
    card.style.cssText=`background:${col.bg};--r:${rot}deg;transform:rotate(${rot}deg);`;
    const tape=document.createElement('div');tape.className='sticky-tape';tape.style.background=col.tape;card.appendChild(tape);
    const meta=document.createElement('div');
    meta.style.cssText='display:flex;align-items:center;gap:5px;margin-bottom:5px';
    meta.innerHTML=n.type==='voice'
      ?`<i class="ph-fill ph-microphone" style="font-size:11px;color:#7f77dd"></i><span style="font-family:'DM Mono',monospace;font-size:10px;color:#9a9688">${timeStr} · voice</span>`
      :`<span style="font-family:'DM Mono',monospace;font-size:10px;color:#9a9688">${timeStr}</span>`;
    card.appendChild(meta);
    const txt=document.createElement('p');
    txt.style.cssText='font-family:"DM Sans",sans-serif;font-size:13px;color:#2a2820;margin:0;line-height:1.55';
    txt.textContent=n.text;card.appendChild(txt);
    const del=document.createElement('button');
    del.setAttribute('aria-label','delete note');
    del.style.cssText='position:absolute;top:8px;right:8px;background:none;border:none;cursor:pointer;color:rgba(26,26,24,.25);padding:2px;line-height:1';
    del.innerHTML='<i class="ph ph-x" style="font-size:12px"></i>';
    del.addEventListener('click',()=>{deleteNote(c,n.id);sbSyncNotes(id);onDelete();});
    card.appendChild(del);
    return card;
  }

  // ── shared: show text input inside a container; calls onSaved() after saving, onCancel() on cancel ──
  function _showTextInput(inputArea, onSaved, onCancel){
    inputArea.innerHTML='';
    const wrap2=document.createElement('div');wrap2.style.cssText='display:flex;flex-direction:column;gap:8px';
    const box=document.createElement('div');box.style.cssText='background:#fffdf5;border-radius:8px;padding:10px 12px;border:1px solid rgba(26,26,24,.1)';
    const ta=document.createElement('textarea');
    ta.placeholder='write anything — feelings, techniques, reminders…';ta.rows=3;
    ta.style.cssText='width:100%;border:none;background:transparent;font-family:"DM Sans",sans-serif;font-size:13px;color:#1a1a18;resize:none;outline:none;box-sizing:border-box;line-height:1.5';
    box.appendChild(ta);wrap2.appendChild(box);
    const btnRow=document.createElement('div');btnRow.style.cssText='display:flex;gap:8px;justify-content:flex-end';
    const cancelBtn=document.createElement('button');
    cancelBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#9a9688;background:none;border:none;cursor:pointer;padding:6px 10px';
    cancelBtn.textContent='cancel';cancelBtn.addEventListener('click',onCancel);
    const saveBtn=document.createElement('button');
    saveBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#f5f1ea;background:#1a1a18;border:none;border-radius:999px;cursor:pointer;padding:7px 16px';
    saveBtn.textContent='add note';
    saveBtn.addEventListener('click',()=>{
      const text=ta.value.trim();if(!text)return;
      addNote(c,text,'text');sbSyncNotes(id);onSaved();
    });
    ta.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))saveBtn.click();});
    btnRow.appendChild(cancelBtn);btnRow.appendChild(saveBtn);
    wrap2.appendChild(btnRow);inputArea.appendChild(wrap2);
    setTimeout(()=>ta.focus(),50);
  }

  // ── shared: show voice input ──
  function _showVoiceInput(inputArea, onSaved, onCancel){
    let _isRecording=false,_recognition=null,_pendingTranscript='';
    inputArea.innerHTML='';_pendingTranscript='';_isRecording=false;
    const wrap2=document.createElement('div');wrap2.style.cssText='display:flex;flex-direction:column;gap:8px';
    const voiceBox=document.createElement('div');
    voiceBox.style.cssText='background:#f3f2ff;border-radius:8px;padding:14px 12px;border:1px solid rgba(127,119,221,.2);text-align:center';
    const micWrap=document.createElement('div');
    micWrap.style.cssText='width:52px;height:52px;border-radius:50%;background:#7f77dd;display:flex;align-items:center;justify-content:center;margin:0 auto 10px;cursor:pointer';
    micWrap.innerHTML='<i class="ph-fill ph-microphone" style="font-size:24px;color:#fff"></i>';
    const statusTxt=document.createElement('p');
    statusTxt.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#7f77dd;margin:0 0 6px';
    statusTxt.textContent='tap to record';
    const transcriptBox=document.createElement('div');
    transcriptBox.style.cssText='display:none;background:#fffdf5;border-radius:6px;padding:8px 10px;font-size:13px;font-family:"DM Sans",sans-serif;color:#1a1a18;text-align:left;margin-top:6px;line-height:1.5;min-height:32px';
    voiceBox.appendChild(micWrap);voiceBox.appendChild(statusTxt);voiceBox.appendChild(transcriptBox);
    wrap2.appendChild(voiceBox);
    const btnRow=document.createElement('div');btnRow.style.cssText='display:flex;gap:8px;justify-content:flex-end';
    const cancelBtn=document.createElement('button');
    cancelBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#9a9688;background:none;border:none;cursor:pointer;padding:6px 10px';
    cancelBtn.textContent='cancel';cancelBtn.addEventListener('click',()=>{if(_recognition)_recognition.stop();onCancel();});
    const saveBtn=document.createElement('button');
    saveBtn.style.cssText='font-family:"DM Mono",monospace;font-size:11px;color:#f5f1ea;background:#7f77dd;border:none;border-radius:999px;cursor:pointer;padding:7px 16px;display:none';
    saveBtn.textContent='save note';
    saveBtn.addEventListener('click',()=>{
      const t=_pendingTranscript.trim();if(!t)return;
      addNote(c,t,'voice');sbSyncNotes(id);onSaved();
    });
    btnRow.appendChild(cancelBtn);btnRow.appendChild(saveBtn);
    wrap2.appendChild(btnRow);inputArea.appendChild(wrap2);
    function _startRecording(){
      _isRecording=true;micWrap.style.background='#e06070';statusTxt.textContent='recording…';micWrap.querySelector('i').classList.add('rec-pulse');
      const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
      if(SR){
        _recognition=new SR();_recognition.continuous=true;_recognition.interimResults=true;
        _recognition.onresult=ev=>{let s='';for(let i=ev.resultIndex;i<ev.results.length;i++)s+=ev.results[i][0].transcript;_pendingTranscript=s;transcriptBox.style.display='block';transcriptBox.textContent=s;};
        _recognition.onend=()=>{_isRecording=false;micWrap.style.background='#7f77dd';statusTxt.textContent='done';micWrap.querySelector('i').classList.remove('rec-pulse');if(_pendingTranscript)saveBtn.style.display='';};
        _recognition.start();
      } else {
        setTimeout(()=>{_pendingTranscript='(voice note)';transcriptBox.style.display='block';transcriptBox.textContent=_pendingTranscript;_isRecording=false;micWrap.style.background='#7f77dd';statusTxt.textContent='done';saveBtn.style.display='';},1200);
      }
    }
    micWrap.addEventListener('click',()=>{if(!_isRecording)_startRecording();else{if(_recognition)_recognition.stop();}});
  }

  // ── main render — called on init and after notes change ──
  function _render(){
    wrap.innerHTML='';
    const notes=(myClassesMap[id]?.notes)||[];

    if(notes.length===0){
      // ── MODE A: no notes → show pill buttons directly ──
      const pillRow=document.createElement('div');pillRow.style.cssText='display:flex;gap:8px';
      const textBtn=document.createElement('button');
      textBtn.className='note-pill-btn';
      textBtn.innerHTML='<i class="ph ph-pencil-simple" style="font-size:14px"></i> text note';
      const voiceBtn=document.createElement('button');
      voiceBtn.className='note-pill-btn';
      voiceBtn.innerHTML='<i class="ph ph-microphone" style="font-size:14px"></i> voice note';
      const inputArea=document.createElement('div');
      function _showPills(){
        wrap.innerHTML='';
        wrap.appendChild(pillRow);
        wrap.appendChild(inputArea);
        inputArea.innerHTML='';
      }
      textBtn.addEventListener('click',()=>{
        pillRow.style.display='none';
        _showTextInput(inputArea,()=>_render(),_showPills);
      });
      voiceBtn.addEventListener('click',()=>{
        pillRow.style.display='none';
        _showVoiceInput(inputArea,()=>_render(),_showPills);
      });
      pillRow.appendChild(textBtn);pillRow.appendChild(voiceBtn);
      wrap.appendChild(pillRow);
      wrap.appendChild(inputArea);

    } else {
      // ── MODE B: has notes → show stickies + add buttons directly (global toggle hides/shows) ──
      const stickyCon=document.createElement('div');
      stickyCon.style.cssText='display:flex;flex-direction:column;gap:10px;margin-bottom:10px';

      function _rebuildStickies(){
        const ns=(myClassesMap[id]?.notes)||[];
        stickyCon.innerHTML='';
        ns.forEach((n,i)=>stickyCon.appendChild(_buildSticky(n,i,false,()=>{
          if(!(myClassesMap[id]?.notes||[]).length)_render();else _rebuildStickies();
        })));
      }

      const inputArea=document.createElement('div');

      function _showAddBtns(){
        inputArea.innerHTML='';
        const row=document.createElement('div');row.style.cssText='display:flex;gap:8px';
        const textBtn=document.createElement('button');
        textBtn.className='note-pill-btn';
        textBtn.innerHTML='<i class="ph ph-pencil-simple" style="font-size:14px"></i> text note';
        textBtn.addEventListener('click',()=>_showTextInput(inputArea,()=>{_rebuildStickies();_showAddBtns();},_showAddBtns));
        const voiceBtn=document.createElement('button');
        voiceBtn.className='note-pill-btn';
        voiceBtn.innerHTML='<i class="ph ph-microphone" style="font-size:14px"></i> voice note';
        voiceBtn.addEventListener('click',()=>_showVoiceInput(inputArea,()=>{_rebuildStickies();_showAddBtns();},_showAddBtns));
        row.appendChild(textBtn);row.appendChild(voiceBtn);
        inputArea.appendChild(row);
      }

      _rebuildStickies();
      _showAddBtns();
      wrap.appendChild(stickyCon);
      wrap.appendChild(inputArea);
    }
  }

  _render();
  return wrap;
}

// ── Add to Calendar ──
function _addToCalendar(c){
  // Parse date_key (YYYY-MM-DD) and start_dt ISO string for accurate datetime
  let dtStart='',dtEnd='';
  try{
    if(c.start_dt){
      const d=new Date(c.start_dt);
      const pad=n=>String(n).padStart(2,'0');
      const fmt=d=>`${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}T${pad(d.getHours())}${pad(d.getMinutes())}00`;
      dtStart=fmt(d);
      // End time: use duration_min if available, else +1 hr
      const dur=(c.duration_min&&c.duration_min>0)?c.duration_min:60;
      const dEnd=new Date(d.getTime()+dur*60000);
      dtEnd=fmt(dEnd);
    } else if(c.date_key){
      // Fallback: all-day event
      const compact=c.date_key.replace(/-/g,'');
      dtStart=compact;dtEnd=compact;
    }
  }catch(e){dtStart=c.date_key?c.date_key.replace(/-/g,''):'';dtEnd=dtStart;}
  const esc=s=>(s||'').replace(/[\\;,]/g,'\\$&').replace(/\n/g,'\\n');
  const uid=`${classId(c).replace(/[^a-z0-9]/gi,'-')}-nyd@dnce.app`;
  const loc=esc(c.studio||'');
  const title=esc(c.class_name+(c.instructor?' w/ '+c.instructor:''));
  const isAllDay=dtStart.length===8;
  const dtProp=isAllDay?`DTSTART;VALUE=DATE:${dtStart}\r\nDTEND;VALUE=DATE:${dtEnd}`:`DTSTART;TZID=America/New_York:${dtStart}\r\nDTEND;TZID=America/New_York:${dtEnd}`;
  const ics=[
    'BEGIN:VCALENDAR','VERSION:2.0','CALSCALE:GREGORIAN','PRODID:-//NYDance//EN',
    'BEGIN:VTIMEZONE','TZID:America/New_York',
    'BEGIN:STANDARD','DTSTART:19671029T020000','RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10','TZOFFSETFROM:-0400','TZOFFSETTO:-0500','TZNAME:EST','END:STANDARD',
    'BEGIN:DAYLIGHT','DTSTART:19870405T020000','RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3','TZOFFSETFROM:-0500','TZOFFSETTO:-0400','TZNAME:EDT','END:DAYLIGHT',
    'END:VTIMEZONE',
    'BEGIN:VEVENT',`UID:${uid}`,dtProp,`SUMMARY:${title}`,`LOCATION:${loc}`,
    'END:VEVENT','END:VCALENDAR'
  ].join('\r\n');
  const blob=new Blob([ics],{type:'text/calendar;charset=utf-8'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download=(c.class_name||'class').replace(/[^a-z0-9 ]/gi,'_')+'.ics';
  document.body.appendChild(a);a.click();
  setTimeout(()=>{URL.revokeObjectURL(url);a.remove();},1000);
}

// ── Notes visibility toggle ──
let _notesHidden=false;
function _toggleNotesHidden(){
  _notesHidden=!_notesHidden;
  document.getElementById('mainScroll').classList.toggle('notes-hidden',_notesHidden);
  const btn=document.getElementById('notesToggleBtn');
  if(btn){
    btn.classList.toggle('active',_notesHidden);
    btn.querySelector('span').textContent=_notesHidden?'Show notes':'Notes';
  }
}

function renderMyClasses(){
  document.querySelector('.app-shell').classList.remove('dark-mode');
  document.getElementById('pageTitle').textContent='My Classes';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  document.getElementById('filterBtn').style.display='none';
  const ntBtn=document.getElementById('notesToggleBtn');
  if(ntBtn)ntBtn.style.display='';
  const listEl=document.getElementById('classesList');
  const stamped=[...ALL_CLASSES,...CUSTOM_CLASSES].filter(c=>isMyClass(c));
  if(!stamped.length){
    listEl.innerHTML=`<div class="empty-state"><div class="empty-icon">🎟️</div><div class="empty-title">No classes stamped yet</div><div class="empty-sub">Tap the stamp icon on any class card to add it here.</div></div>`;
    return;
  }
  // Upcoming first, past at the bottom; within same day sort by start time
  const today=new Date();today.setHours(0,0,0,0);
  const _dk=c=>{const[y,m,d]=c.date_key.split('-').map(Number);return new Date(y,m-1,d);}
  const upcoming=stamped.filter(c=>_dk(c)>=today).sort((a,b)=>a.date_key<b.date_key?-1:a.date_key>b.date_key?1:a.start_hour-b.start_hour);
  const past=stamped.filter(c=>_dk(c)<today).sort((a,b)=>b.date_key<a.date_key?-1:b.date_key>a.date_key?1:b.start_hour-a.start_hour);
  stamped.length=0;[...upcoming,...past].forEach(c=>stamped.push(c));
  listEl.innerHTML='';let lastDate='';
  stamped.forEach((c,i)=>{
    if(c.date_key!==lastDate){
      const div=document.createElement('div');div.className='section-divider date-divider';
      div.innerHTML=`${formatDateFull(c.date_key)}<div class="section-line"></div>`;
      listEl.appendChild(div);lastDate=c.date_key;
    }
    const card=buildCard(c,i,true);
    // Inline notes section
    card.appendChild(_buildInlineNotes(c));
    listEl.appendChild(card);
  });
}

// ── profile tab ──
function renderProfile(){
  document.getElementById('pageTitle').textContent='Profile';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  document.getElementById('filterBtn').style.display='none';
  document.querySelector('.app-shell').classList.remove('dark-mode');
  const ntBtn=document.getElementById('notesToggleBtn');if(ntBtn)ntBtn.style.display='none';
  const listEl=document.getElementById('classesList');

  // Compute stats from stamped classes
  const stamped=[...ALL_CLASSES,...CUSTOM_CLASSES].filter(c=>isMyClass(c));
  const total=stamped.length;
  const upcoming=stamped.filter(c=>{const[y,m,d]=c.date_key.split('-').map(Number);return new Date(y,m-1,d)>=new Date(new Date().setHours(0,0,0,0));}).length;
  const past=total-upcoming;

  // Genre breakdown
  const genreCounts={};
  stamped.forEach(c=>{const g=c.genre||c.subgenre||'other';genreCounts[g]=(genreCounts[g]||0)+1;});
  const topGenres=Object.entries(genreCounts).sort((a,b)=>b[1]-a[1]).slice(0,6);
  const maxG=topGenres[0]?topGenres[0][1]:1;

  // Top studio
  const studioCounts={};
  stamped.forEach(c=>{if(c.studio)studioCounts[c.studio]=(studioCounts[c.studio]||0)+1;});
  const topStudio=Object.entries(studioCounts).sort((a,b)=>b[1]-a[1])[0];

  // Fav instructor
  const instrCounts={};
  stamped.forEach(c=>{if(c.instructor&&c.instructor!=='Modega Staff')instrCounts[c.instructor]=(instrCounts[c.instructor]||0)+1;});
  const topInstr=Object.entries(instrCounts).sort((a,b)=>b[1]-a[1])[0];

  // Notes written
  let noteCount=0;
  Object.values(myClassesMap).forEach(v=>{if(v.notes)noteCount+=v.notes.length;});

  // Wishlist count
  const wishCount=ALL_CLASSES.filter(c=>isSaved(c)).length;

  const email=_currentUserEmail||'';
  const displayName=_currentUserName&&_currentUserName!==email?_currentUserName:'';
  const avatarLetter=(displayName||email||'?')[0].toUpperCase();

  // Genre label map
  const GENRE_LABELS={street:'Street',ballet:'Ballet',contemporary:'Contemp',afro:'Afro',latin:'Latin',heels:'Heels',choreo:'Choreo',conditioning:'Cond.',other:'Other'};

  const genreBarsHTML=topGenres.map(([g,n])=>`
    <div class="genre-bar-row">
      <span class="genre-bar-label">${GENRE_LABELS[g]||g}</span>
      <div class="genre-bar-track"><div class="genre-bar-fill" style="width:${Math.round(n/maxG*100)}%"></div></div>
      <span class="genre-bar-count">${n}</span>
    </div>`).join('');

  const milestones=[5,10,20,30,50,75,100,150,200];
  const next=milestones.find(m=>m>past)||null;
  const milestoneHTML=next
    ? `<div class="stat-sub">${next-past} more to reach ${next} ✦</div>`
    : `<div class="stat-sub">Century dancer 🏆</div>`;

  listEl.innerHTML=`
<div class="profile-pane">
  <div class="profile-hero">
    <div class="profile-hero-label">Classes Taken</div>
    <div class="profile-hero-num">${past}</div>
    ${milestoneHTML}
  </div>
  <div class="profile-email-row">${displayName?`<strong style="color:rgba(200,195,185,.65);font-weight:600">${displayName}</strong> · `:''}${email}</div>
  <div class="profile-grid">
    <div class="stat-card">
      <div class="stat-label">Upcoming</div>
      <div class="stat-num">${upcoming}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Wishlisted</div>
      <div class="stat-num">${wishCount}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Notes</div>
      <div class="stat-num">${noteCount}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Pop-ups</div>
      <div class="stat-num">${CUSTOM_CLASSES.length}</div>
    </div>
    ${topInstr?`<div class="stat-card full">
      <div class="stat-label">Favourite Teacher</div>
      <div class="stat-name">${topInstr[0]}</div>
      <div class="stat-sub">${topInstr[1]} class${topInstr[1]>1?'es':''} together</div>
    </div>`:''}
    ${topStudio?`<div class="stat-card full">
      <div class="stat-label">Favourite Studio</div>
      <div class="stat-name">${topStudio[0]}</div>
      <div class="stat-sub">${topStudio[1]} visit${topStudio[1]>1?'s':''}</div>
    </div>`:''}
    ${topGenres.length?`<div class="stat-card full">
      <div class="stat-label">By Style</div>
      <div class="genre-bars">${genreBarsHTML}</div>
    </div>`:''}
  </div>
</div>`;
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
  level:new Set(['All Levels','Adv Beg','Intermediate','Int/Adv']),
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
  document.querySelector('.app-shell').classList.remove('dark-mode');
  document.getElementById('pageTitle').textContent='Wishlist';
  document.getElementById('weekStrip').style.display='none';
  document.getElementById('updatedText').style.visibility='hidden';
  document.getElementById('filterBtn').style.display='none';
  const ntBtn2=document.getElementById('notesToggleBtn');
  if(ntBtn2)ntBtn2.style.display='';
  const listEl=document.getElementById('classesList');
  listEl.innerHTML='';

  // ── Pop Ups section (top) ──
  const popHeader=document.createElement('div');
  popHeader.className='saved-section-header';
  popHeader.innerHTML='<i class="ph ph-sparkle"></i> Pop Ups';
  listEl.appendChild(popHeader);

  // Single FAB add button
  const popupWrap=document.createElement('div');
  popupWrap.className='popup-pane';popupWrap.style.paddingTop='8px';
  popupWrap.innerHTML=`
    <button class="popup-add-fab" id="popupAddFab"><i class="ph ph-plus-circle"></i> Add a class</button>
    <div id="popupAddOptions" style="display:none">
      <div class="popup-add-options">
        <button class="popup-add-opt" id="popupManualBtn"><i class="ph ph-pencil-simple"></i>Manual</button>
        <button class="popup-add-opt" id="popupGalleryBtn"><i class="ph ph-image"></i>Gallery
          <input type="file" id="popupPhotoInput" accept="image/*" style="position:absolute;opacity:0;width:0;height:0;pointer-events:none"/>
        </button>
        <button class="popup-add-opt" id="popupPasteBtn"><i class="ph ph-clipboard-text"></i>Paste</button>
      </div>
    </div>
    <div id="popupOcrStatus" class="popup-ocr-status" style="display:none"></div>
    <div id="popupManualWrap"></div>
    <div id="popupContent" class="popup-content-area" style="display:none"></div>
    <div id="popupSummary" class="popup-summary" style="display:none"></div>
    <button class="popup-save-btn" id="popupSaveBtn" style="display:none"><i class="ph ph-bookmark-simple"></i>Save to Pop Ups</button>`;
  listEl.appendChild(popupWrap);

  // Wire FAB toggle
  _popupParsed=null;
  let _fabOpen=false;
  document.getElementById('popupAddFab').addEventListener('click',()=>{
    _fabOpen=!_fabOpen;
    document.getElementById('popupAddOptions').style.display=_fabOpen?'':'none';
    const fab=document.getElementById('popupAddFab');
    fab.innerHTML=_fabOpen?'<i class="ph ph-x-circle"></i> Cancel':'<i class="ph ph-plus-circle"></i> Add a class';
  });

  // Manual
  let _manualOpen=false;
  document.getElementById('popupManualBtn').addEventListener('click',()=>{
    _manualOpen=!_manualOpen;
    const wrap=document.getElementById('popupManualWrap');
    if(_manualOpen){renderManualForm(wrap);}else{wrap.innerHTML='';}
  });

  // Gallery (photo)
  document.getElementById('popupGalleryBtn').addEventListener('click',()=>{
    document.getElementById('popupPhotoInput').click();
  });
  document.getElementById('popupPhotoInput').addEventListener('change',handlePopupPhoto);

  // Paste
  document.getElementById('popupPasteBtn').addEventListener('click',async()=>{
    const status=document.getElementById('popupOcrStatus');
    try{
      const text=await navigator.clipboard.readText();
      if(text){
        const ca=document.getElementById('popupContent');ca.style.display='';
        ca.innerHTML=`<textarea class="popup-textarea" readonly>${esc(text)}</textarea>`;
        const cls=parseClassText(text);if(cls)_showParsedSummary(cls);
      }
    }catch(e){
      const ca=document.getElementById('popupContent');ca.style.display='';
      ca.innerHTML='<textarea id="popupManualTA" class="popup-textarea" placeholder="Paste your text here…"></textarea>';
      document.getElementById('popupManualTA').focus();
      document.getElementById('popupManualTA').addEventListener('input',function(){
        clearTimeout(window._ppD);
        window._ppD=setTimeout(()=>{const cls=parseClassText(this.value);if(cls)_showParsedSummary(cls);},600);
      });
      if(status){status.style.display='';status.textContent='Tap & hold the box above, then choose Paste.';setTimeout(()=>{status.style.display='none';},4000);}
    }
  });
  document.getElementById('popupSaveBtn').addEventListener('click',doSaveCustomClass);

  // Custom classes list
  const sorted=[...CUSTOM_CLASSES].sort((a,b)=>b.date_key.localeCompare(a.date_key));
  if(sorted.length){
    const customHeader=document.createElement('div');
    customHeader.className='popup-classes-header';
    customHeader.textContent=`Your Pop-ups (${sorted.length})`;
    listEl.appendChild(customHeader);
    sorted.forEach((c,i)=>{
      const card=buildCard(c,i,false);
      listEl.appendChild(card);
    });
  }

  // ── Wishlist section (bottom) ──
  const wlHeader=document.createElement('div');
  wlHeader.className='saved-section-header';
  wlHeader.style.marginTop='28px';
  wlHeader.innerHTML='<i class="ph ph-shooting-star"></i> Wishlist';
  listEl.appendChild(wlHeader);

  const savedFromSchedule=ALL_CLASSES.filter(c=>isSaved(c));
  if(!savedFromSchedule.length){
    const empty=document.createElement('div');
    empty.className='empty-state';empty.style.paddingTop='16px';
    empty.innerHTML='<div class="empty-icon">🔖</div><div class="empty-title">No saved classes yet</div><div class="empty-sub">Tap ★ on any card to save it here.</div>';
    listEl.appendChild(empty);
  } else {
    savedFromSchedule.sort((a,b)=>a.date_key<b.date_key?-1:a.date_key>b.date_key?1:a.start_hour-b.start_hour);
    let lastDate='';
    savedFromSchedule.forEach((c,i)=>{
      if(c.date_key!==lastDate){
        const div=document.createElement('div');div.className='section-divider date-divider';
        div.innerHTML=`${formatDateFull(c.date_key)}<div class="section-line"></div>`;
        listEl.appendChild(div);lastDate=c.date_key;
      }
      const card=buildCard(c,i);
      const cid=classId(c);
      if(!myClassesMap[cid])myClassesMap[cid]={notes:[],added_at:null,_wishlistOnly:true};
      card.appendChild(_buildInlineNotes(c));
      listEl.appendChild(card);
    });
  }
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

function buildCard(c,i,inMyClasses){
  const past=isPastClass(c);
  const div=document.createElement('div');
  // Past muting only on schedule tab; My Classes shows full card so stamp is visible
  div.className=`card ${cardStyle(c)}${c.is_canceled?' card-canceled':''}${past&&!inMyClasses?' card-past':''}`;
  div.style.animationDelay=`${Math.min(i*35,200)}ms`;

  const color=avatarColor(c.instructor);
  const abbr=initials(c.instructor);
  const timeStr=c.start_display?(c.end_display?`${c.start_display} – ${c.end_display}`:c.start_display):'';
  const dayAbbr=c.date_key?(()=>{const[y,mo,d]=c.date_key.split('-').map(Number);return DAY_LETTERS[new Date(y,mo-1,d).getDay()]})():'';
  const metaStr=c.studio+(dayAbbr?' · '+dayAbbr:'')+(timeStr?' · '+timeStr:'');
  const saved=isSaved(c);
  const stamped=isMyClass(c);
  const customTag=c.is_custom?'<span class="custom-tag">✦ POP UP</span>':'';

  let capHTML='';
  if(c.max_capacity>0&&c.total_booked!=null){
    const pct=Math.min(100,Math.round(c.total_booked/c.max_capacity*100));
    const spots=c.max_capacity-c.total_booked;
    const capText=spots<=0?'Full':spots<=5?`${spots} spots left`:`${c.total_booked}/${c.max_capacity}`;
    capHTML=`<div class="cap-wrap"><div class="cap-bar-bg"><div class="cap-bar-fill" style="width:${pct}%"></div></div><div class="cap-text">${capText}</div></div>`;
  }
  const bookHref=c.booking_url&&!c.is_canceled?`<a href="${esc(c.booking_url)}" target="_blank" rel="noopener" class="card-tap" aria-label="Book ${esc(c.class_name)}"></a>`:'';

  // In My Classes tab: three-dots menu instead of stamp+star buttons
  const actionsHTML=inMyClasses
    ?`<button class="mc-dots-btn" aria-label="Options"><i class="ph ph-dots-three"></i></button>`
    :`<button class="my-btn${stamped?' stamped':''}" aria-label="${stamped?'Unmark':'Mark as attended'}">
        <i class="${stamped?'ph-fill':'ph'} ph-stamp"></i>
      </button>
      <button class="save-btn${saved?' saved':''}" aria-label="${saved?'Unsave':'Save'}">
        <i class="${saved?'ph-fill':'ph'} ph-shooting-star"></i>
      </button>`;

  div.innerHTML=`${bookHref}
    <div class="card-inner">
      <div class="card-header-row">
        <div class="card-meta">${customTag}${esc(metaStr)}</div>
        <div class="card-actions">${actionsHTML}</div>
      </div>
      <div class="card-name">${esc(c.class_name)}</div>
      <div class="card-instructor-row">
        <div class="small-avatar" style="background:${color}">${abbr}</div>
        <span class="card-instructor-name">${esc(c.instructor||'—')}</span>
      </div>
      ${capHTML}
    </div>`;

  if(inMyClasses){
    // Three-dots → dropdown with Remove option
    if(stamped)_attachStamp(div,c,false);
    div.querySelector('.mc-dots-btn').addEventListener('click',e=>{
      e.preventDefault();e.stopPropagation();
      // Remove any existing menus
      document.querySelectorAll('.mc-dots-menu').forEach(m=>m.remove());
      const menu=document.createElement('div');
      menu.className='mc-dots-menu';
      menu.innerHTML=`<button class="mc-dots-item mc-dots-cal"><i class="ph ph-calendar-blank"></i> Add to Calendar</button><button class="mc-dots-item mc-dots-delete"><i class="ph ph-trash"></i> Remove from My Classes</button>`;
      menu.querySelector('.mc-dots-cal').addEventListener('click',ev=>{
        ev.stopPropagation();
        menu.remove();
        _addToCalendar(c);
      });
      menu.querySelector('.mc-dots-delete').addEventListener('click',ev=>{
        ev.stopPropagation();
        menu.remove();
        toggleMyClass(c); // removes it
        setTimeout(renderMyClasses,60);
      });
      // Position below the button
      const btnRect=e.currentTarget.getBoundingClientRect();
      menu.style.cssText=`position:fixed;right:${window.innerWidth-btnRect.right}px;top:${btnRect.bottom+4}px;z-index:999`;
      document.body.appendChild(menu);
      // Dismiss on outside click
      setTimeout(()=>document.addEventListener('click',function _d(){menu.remove();document.removeEventListener('click',_d);},{once:true}),0);
    });
  } else {
    div.querySelector('.save-btn').addEventListener('click',e=>{
      e.preventDefault();e.stopPropagation();
      const nowSaved=toggleSaved(c);
      const btn=e.currentTarget;
      btn.classList.toggle('saved',nowSaved);
      btn.setAttribute('aria-label',nowSaved?'Unsave':'Save');
      btn.querySelector('i').className=(nowSaved?'ph-fill':'ph')+' ph-shooting-star';
      if(S.tab==='saved')setTimeout(renderSaved,60);
    });
    if(stamped)_attachStamp(div,c,false);
    div.querySelector('.my-btn').addEventListener('click',e=>{
      e.preventDefault();e.stopPropagation();
      const nowStamped=toggleMyClass(c);
      const btn=e.currentTarget;
      btn.classList.toggle('stamped',nowStamped);
      btn.setAttribute('aria-label',nowStamped?'Unmark':'Mark as attended');
      btn.querySelector('i').className=(nowStamped?'ph-fill':'ph')+' ph-stamp';
      const existing=div.querySelector('.stamp-mark');
      if(nowStamped){if(!existing)_attachStamp(div,c,true);}
      else{if(existing)existing.remove();}
      if(S.tab==='myclasses')setTimeout(renderMyClasses,60);
    });
  }
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
function _navTabEl(tab){const m={schedule:'navSchedule',wishlist:'navWishlist',myclasses:'navMyclasses',profile:'navProfile'};return document.getElementById(m[tab]);}

function snapCapsule(tabEl){
  const c=document.getElementById('navCapsule');
  if(!c||!tabEl)return;
  c.style.transition='none';
  c.getBoundingClientRect(); // force reflow
  c.style.left=tabEl.offsetLeft+'px';
  c.style.width=tabEl.offsetWidth+'px';
  requestAnimationFrame(()=>{c.style.transition='';});
}

// ── tab switching ──
function switchTab(tab){
  if(_navBusy)return;
  if(tab===_navCurrent)return;
  const _ntBtn=document.getElementById('notesToggleBtn');
  if(tab==='schedule'){
    _animateNav('schedule',()=>{
      document.querySelector('.app-shell').classList.remove('dark-mode');
      document.getElementById('weekStrip').style.display='';
      document.getElementById('updatedText').style.visibility='visible';
      renderAll();
    });
    S.tab='schedule';
    if(_ntBtn)_ntBtn.style.display='none';
  } else if(tab==='wishlist'){
    _animateNav('wishlist',()=>renderSaved());
    S.tab='saved';
    if(_ntBtn)_ntBtn.style.display='';
  } else if(tab==='profile'){
    _animateNav('profile',()=>renderProfile());
    S.tab='profile';
    if(_ntBtn)_ntBtn.style.display='none';
  } else {
    _animateNav('myclasses',()=>renderMyClasses());
    S.tab='myclasses';
  }
  localStorage.setItem('nyd_tab',tab);
}

function _animateNav(newTab,callback){
  if(_navBusy)return;
  _navBusy=true;
  const oldEl=_navTabEl(_navCurrent);
  const newEl=_navTabEl(newTab);
  const capsule=document.getElementById('navCapsule');

  // Step 1: measure new tab's position NOW (before expansion) and start sliding capsule
  const startLeft=newEl.offsetLeft;
  const startW=newEl.offsetWidth;
  capsule.style.left=startLeft+'px';
  capsule.style.width=startW+'px';

  // Step 2: swap active classes — CSS handles label expand/collapse transitions
  oldEl.classList.remove('active');
  newEl.classList.add('active');
  _navCurrent=newTab;

  // Step 3: once the label CSS transition finishes (~380ms), snap capsule to final size
  setTimeout(()=>{
    capsule.style.transition='none';
    capsule.getBoundingClientRect();
    capsule.style.left=newEl.offsetLeft+'px';
    capsule.style.width=newEl.offsetWidth+'px';
    requestAnimationFrame(()=>{
      capsule.style.transition='';
      _navBusy=false;
    });
  },400);

  callback();
}

// ── event listeners ──
document.getElementById('rangeMin').addEventListener('input',updateSlider);
document.getElementById('rangeMax').addEventListener('input',updateSlider);
document.getElementById('filterBtn').addEventListener('click',openDrawer);
document.getElementById('drawerClose').addEventListener('click',closeDrawer);
document.getElementById('notesToggleBtn').addEventListener('click',_toggleNotesHidden);
document.getElementById('drawerOverlay').addEventListener('click',closeDrawer);
document.getElementById('applyBtn').addEventListener('click',()=>{saveFilters();closeDrawer();renderAll()});
document.getElementById('teacherSearch').addEventListener('input',buildTeacherChips);
['navSchedule','navWishlist','navMyclasses','navProfile'].forEach(id=>{
  document.getElementById(id).addEventListener('click',()=>{
    if(_navBusy)return;
    const tab=id==='navSchedule'?'schedule':id==='navWishlist'?'wishlist':id==='navMyclasses'?'myclasses':'profile';
    switchTab(tab);
  });
});

// ── Login form ──
document.getElementById('loginBtn').addEventListener('click',async()=>{
  const name=document.getElementById('loginName').value.trim();
  const email=document.getElementById('loginEmail').value.trim();
  const errEl=document.getElementById('loginError');
  errEl.style.display='none';
  if(!email||!email.includes('@')){errEl.textContent='Please enter a valid email.';errEl.style.display='block';return;}
  const btn=document.getElementById('loginBtn');
  btn.disabled=true;btn.textContent='SENDING…';
  if(name)localStorage.setItem('nyd_pending_name',name);
  const _redirectTo=(location.hostname==='localhost'||location.protocol==='file:')?'https://nyc-dance-rho.vercel.app':location.origin+'/';
  const{error}=await _sb.auth.signInWithOtp({email,options:{emailRedirectTo:_redirectTo,data:{display_name:name||undefined}}});
  if(error){
    console.error('[Auth] signInWithOtp error:',JSON.stringify(error),error);
    const msg=error.message||error.error_description||JSON.stringify(error)||'Something went wrong — try again.';
    errEl.textContent=msg;errEl.style.display='block';
    btn.disabled=false;btn.textContent='SEND MAGIC LINK →';
  } else {
    document.getElementById('loginForm').style.display='none';
    document.getElementById('loginSentEmail').textContent=email;
    document.getElementById('loginSent').style.display='block';
  }
});
['loginEmail','loginName'].forEach(id=>{
  document.getElementById(id).addEventListener('keydown',e=>{if(e.key==='Enter')document.getElementById('loginBtn').click();});
});


function renderAll(){
  const _ntB=document.getElementById('notesToggleBtn');if(_ntB)_ntB.style.display='none';
  document.getElementById('filterBtn').style.display='';
  renderCalendar();renderClasses();
}

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
  syncChipsFromState();buildTeacherChips();
  // Restore last active tab — render the right content immediately, no flash
  const _savedTab=localStorage.getItem('nyd_tab');
  const _tabNav={schedule:'navSchedule',wishlist:'navWishlist',myclasses:'navMyclasses',profile:'navProfile'};
  if(_savedTab&&_savedTab!=='schedule'&&_tabNav[_savedTab]){
    document.getElementById('navSchedule').classList.remove('active');
    document.getElementById(_tabNav[_savedTab]).classList.add('active');
    _navCurrent=_savedTab;
    if(_savedTab==='myclasses'){S.tab='myclasses';document.getElementById('weekStrip').style.display='none';document.getElementById('updatedText').style.visibility='hidden';renderMyClasses();}
    else if(_savedTab==='wishlist'){S.tab='saved';document.getElementById('weekStrip').style.display='none';document.getElementById('updatedText').style.visibility='hidden';renderSaved();}
    else if(_savedTab==='profile'){S.tab='profile';document.getElementById('weekStrip').style.display='none';document.getElementById('updatedText').style.visibility='hidden';renderProfile();}
  } else {
    renderAll();
  }
  // Snap capsule to active tab after Phosphor icons load (they affect icon size)
  const _initCapsule=()=>{
    const activeEl=_navTabEl(_navCurrent);
    if(activeEl)snapCapsule(activeEl);
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
