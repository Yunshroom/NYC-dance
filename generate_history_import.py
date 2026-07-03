#!/usr/bin/env python3
"""
Parse MindBody completed class history and generate a JS console snippet
that imports them into the NYC Dance app's my_classes Supabase table.
"""

import json
import re

# ── Studio mapping ─────────────────────────────────────────────────────────────
STUDIO_MAP = {
    "Brickhouse NYC":           ("Brickhouse NYC",          "brickhouse"),
    "Peridance Center":         ("Peridance",               "peridance"),
    "PJM DANCE NYC":            ("PJM Dance",               "pjm"),
    "Steps on Broadway":        ("Steps on Broadway",       "steps"),
    "Playground LA":            ("Playground LA",           "playgroundla"),
    "MOVEMENT LIFESTYLE":       ("Movement Lifestyle",      "movementlifestyle"),
    "Millennium Dance Complex":  ("Millennium Dance Complex","millennium"),
    "DanceLife X":              ("DanceLife X",             "dancelifex"),
    "Exit Space":               ("Exit Space",              "exitspace"),
}

MONTHS = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12
}

def parse_time(t, tz_offset):
    """Parse '12:00pm' or '6:30pm PDT' → (hour_float, display_str, iso_time_str)"""
    t = t.strip().replace("PDT","").replace("PST","").replace("EDT","").replace("EST","").strip()
    m = re.match(r'(\d+):(\d+)(am|pm)', t, re.I)
    if not m:
        return None, "", ""
    h, mi, ampm = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ampm == "pm" and h != 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    hour_float = h + mi/60
    display = f"{m.group(1)}:{m.group(2)} {'AM' if ampm=='am' else 'PM'}"
    tz = f"{tz_offset:+03d}:00"
    time_str = f"{h:02d}:{mi:02d}:00{tz}"
    return hour_float, display, time_str

def extract_genre(name):
    n = name.lower()
    if any(x in n for x in ['ballet','pointe','barre']):
        return 'ballet','ballet'
    if any(x in n for x in ['vogue','new way','old way']):
        return 'street','vogue'
    if any(x in n for x in ['waack','whack']):
        return 'street','waacking'
    if 'house' in n:
        return 'street','house'
    if any(x in n for x in ['breaking','bboy','bgirl']):
        return 'street','breaking'
    if 'popping' in n:
        return 'street','popping'
    if 'locking' in n:
        return 'street','locking'
    if 'krump' in n:
        return 'street','krump'
    if any(x in n for x in ['afro','african']):
        return 'afro','afrobeats'
    if any(x in n for x in ['contemporary','contemp']):
        return 'contemporary','contemporary'
    if 'modern' in n:
        return 'contemporary','modern'
    if 'lyrical' in n:
        return 'contemporary','lyrical'
    if any(x in n for x in ['jazz funk','jazzfunk','street jazz']):
        return 'street','jazzfunk'
    if any(x in n for x in ['kpop','k-pop','kpop cover','chinese style']):
        return 'street','kpop'
    if any(x in n for x in ['salsa','mambo','bachata','latin']):
        return 'latin','latin'
    if any(x in n for x in ['heel','femme','stiletto']):
        return 'heels','heels'
    if any(x in n for x in ['choreography','choreo','commercial']):
        return 'choreo','choreo'
    if any(x in n for x in ['hip hop','hip-hop','hiphop']):
        return 'street','hiphop'
    if 'jazz' in n:
        return 'contemporary','jazz'
    if any(x in n for x in ['yoga','condition','pilates','stretch']):
        return 'conditioning','conditioning'
    return 'other','other'

def extract_level(name):
    n = name.lower()
    if any(x in n for x in ['adv. beg','adv beg','beg./adv','adv/beg','beginner/intermediate']):
        return 'Adv Beg'
    if any(x in n for x in ['beginner','beg.','beg ',' beg','beginning','level 1']):
        return 'Beginner'
    if any(x in n for x in ['all level','open level','all-level']):
        return 'All Levels'
    if any(x in n for x in ['int./adv','int/adv','intermediate/adv','int adv']):
        return 'Int/Adv'
    if any(x in n for x in ['intermediate','inter ','inter.','level 2','level 3']):
        return 'Intermediate'
    if any(x in n for x in ['advanced','adv ','adv.']):
        return 'Advanced'
    return 'All Levels'

def slugify(s):
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')[:40]

# ── Raw class data ──────────────────────────────────────────────────────────────
CLASSES = [
    # (day, month_name, year, time_str, duration_min, class_name, studio_raw, instructor, tz_offset)
    (27,"June",2026,"12:00pm",90,"Beg House","Peridance Center","Huu Rock",-4),
    (20,"June",2026,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (20,"June",2026,"3:30pm",90,"Pop Up: Adv Beg Choreography - Karin Furui","PJM DANCE NYC","Peter Chow",-4),
    (19,"June",2026,"5:00pm",90,"Hip Hop (Int/Adv)","Brickhouse NYC","Jojo Brooks",-4),
    (1,"May",2026,"4:00pm",90,"Inter Choreography","Peridance Center","Kara Lee",-4),
    (28,"April",2026,"7:00pm",90,"Adv Choreography","Peridance Center","Kenichi Kasamatsu",-4),
    (25,"April",2026,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (10,"April",2026,"4:00pm",90,"Inter Choreography","Peridance Center","Kara Lee",-4),
    (15,"March",2026,"3:00pm",90,"Jazz (Int/Adv)","Playground LA","Gianina",-7),
    (15,"March",2026,"1:00pm",90,"Hip Hop (Beg/Int)","Playground LA","Gigi Escobar",-7),
    (14,"March",2026,"3:30pm",90,"Choreo (Int/Adv)","MOVEMENT LIFESTYLE","Derrell Bullock",-7),
    (14,"March",2026,"12:30pm",90,"Contemporary","Millennium Dance Complex","Hannah Gallagher",-7),
    (14,"March",2026,"9:30am",90,"Beginning Hip Hop 1","Millennium Dance Complex","André Maya",-7),
    (10,"January",2026,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-5),
    (7,"January",2026,"7:00pm",90,"Adv Choreography","Peridance Center","Esosa Oviasu",-5),
    (18,"December",2025,"4:30pm",90,"Street Jazz (Int/Adv)","Brickhouse NYC","Masumi Kambayashi",-5),
    (2,"December",2025,"7:00pm",90,"Adv Choreography","Peridance Center","Masumi Kambayashi",-5),
    (1,"December",2025,"7:00pm",90,"Adv Choreography","Peridance Center","Bo Park",-5),
    (30,"November",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Jana Hicks",-5),
    (30,"November",2025,"10:00am",90,"Adv Beg Contemporary","Peridance Center","Miho Ryu",-5),
    (21,"November",2025,"8:00pm",90,"Pop Up - Hip Hop","Brickhouse NYC","Elliot YJ You",-5),
    (8,"November",2025,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-5),
    (8,"November",2025,"5:00pm",90,"Pop Up - Choreography","Brickhouse NYC","Florien Bennema",-5),
    (7,"October",2025,"7:00pm",90,"Adv Choreography","Peridance Center","Masumi Kambayashi",-4),
    (27,"September",2025,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (14,"September",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Marijke Eliasberg",-4),
    (14,"September",2025,"11:30am",90,"Inter Contemporary","Peridance Center","Miho Ryu",-4),
    (31,"August",2025,"6:15pm",120,"In-Studio Spotlight: Int/Adv Contemporary","Steps on Broadway","Brandon Coleman",-4),
    (31,"August",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Jana Hicks",-4),
    (28,"August",2025,"7:00pm",90,"Inter Contemporary","Peridance Center","Destany Churchwell",-4),
    (28,"August",2025,"5:30pm",90,"Inter Hip Hop","Peridance Center","Cebo Carr",-4),
    (26,"August",2025,"7:00pm",90,"Adv Choreography","Peridance Center","Karen Vanessa",-4),
    (24,"August",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Jana Hicks",-4),
    (16,"August",2025,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (15,"August",2025,"6:30pm",90,"Pop Up - Hip Hop","Brickhouse NYC","Tokumi Watanabe",-4),
    (14,"August",2025,"6:30pm",90,"In-Studio Int/Adv Contemporary Fusion","Steps on Broadway","Cat Cogliandro",-4),
    (2,"August",2025,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (20,"July",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Jana Hicks",-4),
    (18,"July",2025,"4:00pm",90,"Inter Choreography","Peridance Center","Kara Lee",-4),
    (17,"July",2025,"4:30pm",90,"Street Jazz (Int/Adv)","Brickhouse NYC","Masumi Kambayashi",-4),
    (14,"July",2025,"5:30pm",90,"Inter Contemporary","Peridance Center","Emily Greenwell",-4),
    (14,"July",2025,"4:00pm",90,"Inter Countertechnique","Peridance Center","Griffin Massey",-4),
    (5,"July",2025,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (29,"June",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Jana Hicks",-4),
    (29,"June",2025,"11:30am",90,"Inter Contemporary","Peridance Center","Miho Ryu",-4),
    (28,"June",2025,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (22,"June",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Marijke Eliasberg",-4),
    (22,"June",2025,"11:30am",90,"Inter Contemporary","Peridance Center","Vive",-4),
    (21,"June",2025,"8:00pm",90,"Pop Up - Choreography","Brickhouse NYC","Diezel Morar",-4),
    (21,"June",2025,"6:30pm",90,"Choreography (Int/Adv)","Brickhouse NYC","Roy Garzon",-4),
    (19,"June",2025,"4:30pm",90,"Street Jazz (Int/Adv)","Brickhouse NYC","Masumi Kambayashi",-4),
    (19,"June",2025,"2:30pm",90,"Inter Choreography","Peridance Center","Tomoko Ishikawa",-4),
    (8,"June",2025,"1:15pm",90,"Inter Contemporary","Peridance Center","Marijke Eliasberg",-4),
    (8,"June",2025,"11:30am",90,"Inter Contemporary","Peridance Center","Vive",-4),
    (7,"June",2025,"4:30pm",90,"Inter Contemporary","Peridance Center","Ali Koinoglou",-4),
    (4,"June",2025,"5:30pm",90,"Adv Choreography","Peridance Center","Sam Javi",-4),
    (2,"June",2025,"6:00pm",120,"Pop Up - Hip Hop","Brickhouse NYC","Gabe De Guzman",-4),
    (1,"June",2025,"1:00pm",90,"Inter Contemporary","Peridance Center","Marijke Eliasberg",-4),
    (1,"June",2025,"11:30am",90,"Inter Contemporary","Peridance Center","Vive",-4),
    (31,"May",2025,"5:00pm",90,"Pop Up - Choreography","Brickhouse NYC","Ishanathan Guteng",-4),
    (5,"February",2025,"8:30pm",75,"Commercial Choreography (Level 2)","DanceLife X","Hazel Deng",-5),
    (5,"February",2025,"7:15pm",75,"Jazz Funk (Level 2)","DanceLife X","Steven Chau",-5),
    (31,"January",2025,"8:30pm",75,"Beginner/Intermediate Chinese Style Jazz","DanceLife X","Quentin Wong",-5),
    (31,"January",2025,"7:15pm",75,"Commercial Choreography (Level 3)","DanceLife X","Alejandro Chica",-5),
    (31,"January",2025,"6:00pm",60,"KPOP Cover Class","DanceLife X","Lucas Niu",-5),
    (24,"January",2025,"8:30pm",75,"Beginner/Intermediate Chinese Style Jazz","DanceLife X","Quentin Wong",-5),
    (24,"January",2025,"7:15pm",75,"Commercial Choreography (Level 3)","DanceLife X","Alejandro Chica",-5),
    (27,"April",2022,"6:30pm",90,"Int/Adv Modern","Exit Space","Marlo Martin",-7),
    (20,"April",2022,"6:30pm",90,"Int/Adv Modern","Exit Space","Marlo Martin",-7),
]

def build_class(day, month_name, year, time_str, duration_min, class_name, studio_raw, instructor, tz_offset):
    mo = MONTHS[month_name]
    date_key = f"{year}-{mo:02d}-{day:02d}"
    hour_float, start_display, time_part = parse_time(time_str, tz_offset)
    start_iso = f"{date_key}T{time_part}"

    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=tz_offset))
    try:
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = start_dt + timedelta(minutes=duration_min)
        end_h = end_dt.hour % 12 or 12
        end_ampm = "AM" if end_dt.hour < 12 else "PM"
        end_display = f"{end_h}:{end_dt.minute:02d} {end_ampm}"
    except:
        end_display = ""

    studio_display, studio_key = STUDIO_MAP.get(studio_raw, (studio_raw, slugify(studio_raw)))
    genre, subgenre = extract_genre(class_name)
    level = extract_level(class_name)
    class_id = f"history:{date_key}:{studio_key}:{slugify(class_name)}"

    return {
        "class_id": class_id,
        "class_json": {
            "studio":        studio_display,
            "studio_key":    studio_key,
            "class_name":    class_name,
            "category":      "",
            "instructor":    instructor,
            "date_key":      date_key,
            "start_dt":      start_iso,
            "start_display": start_display,
            "end_display":   end_display,
            "duration_min":  duration_min,
            "level":         level,
            "genre":         genre,
            "subgenre":      subgenre,
            "start_hour":    hour_float,
            "is_canceled":   False,
            "booking_url":   "",
            "max_capacity":  None,
            "total_booked":  None,
            "description":   "",
            "notes":         [],
            "added_at":      start_iso,
            "is_history":    True,
        },
        "added_at": start_iso,
    }

records = [build_class(*c) for c in CLASSES]

# Generate JS snippet
js = f"""
// NYC Dance — history import ({len(records)} classes)
// Run this in the console on nyc-dance-rho.vercel.app while logged in
(async function importHistory() {{
  if (!_sb || !_SB_USER) {{ console.error('Not logged in'); return; }}
  const rows = {json.dumps([{
    "user_id": "__USER__",
    "class_id": r["class_id"],
    "class_json": r["class_json"],
    "added_at": r["added_at"]
  } for r in records], separators=(',',':'))};
  const withUser = rows.map(r => ({{...r, user_id: _SB_USER}}));
  console.log('Importing', withUser.length, 'classes…');
  const {{ error }} = await _sb.from('my_classes').upsert(withUser, {{onConflict:'user_id,class_id'}});
  if (error) {{ console.error('Import error:', error); }}
  else {{ console.log('✅ Import complete! Reloading…'); location.reload(); }}
}})();
""".strip()

out = "/Users/yangyun/Penske/scraper/history_import.js"
with open(out, "w") as f:
    f.write(js)

print(f"Generated {out}")
print(f"Total dance classes: {len(records)}")
print("\nPaste the content of history_import.js in the app console.")
