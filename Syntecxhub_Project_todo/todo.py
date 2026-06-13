#!/usr/bin/env python3
"""
To-Do List Manager — interactive menu + direct CLI.
Zero external dependencies (standard library only).

Interactive mode (default):  python todo.py
Direct CLI examples:
  python todo.py add "Buy groceries" --due 2026-12-31 --priority high --tags shopping
  python todo.py add --ai "submit report by Friday, tag it work, urgent"
  python todo.py list / list --priority high / list --tag work
  python todo.py overdue
  python todo.py done 3 / delete 3
  python todo.py edit 3 --title "New title" --due 2026-12-25
"""

import argparse
import re
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# ── ANSI helpers ─────────────────────────────────────────────────────────────

_NO_COLOR = not sys.stdout.isatty()

def _c(code: str, t: str) -> str:
    return t if _NO_COLOR else f"\033[{code}m{t}\033[0m"

RED      = lambda t: _c("31",    t)
YELLOW   = lambda t: _c("33",    t)
GREEN    = lambda t: _c("32",    t)
CYAN     = lambda t: _c("36",    t)
MAGENTA  = lambda t: _c("35",    t)
BLUE     = lambda t: _c("34",    t)
BOLD     = lambda t: _c("1",     t)
DIM      = lambda t: _c("2",     t)
RED_BOLD = lambda t: _c("1;31",  t)

PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": GREEN}

EVENT_ICONS = {
    "birthday": "🎂", "meeting": "📅", "deadline": "⏰",
    "holiday": "🎉",  "other": "📌",   None: "  ",
}


# ── Database ──────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "tasks.db"

_DDL_TASKS = """\
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL,
    due_date   TEXT,
    due_time   TEXT,
    priority   TEXT    NOT NULL DEFAULT 'medium',
    importance INTEGER,
    event_type TEXT,
    tags       TEXT    NOT NULL DEFAULT '',
    completed  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL,
    recurring  TEXT
);"""

_DDL_REMINDERS = """\
CREATE TABLE IF NOT EXISTS reminders (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    notify_at TEXT    NOT NULL,
    message   TEXT    NOT NULL DEFAULT '',
    fired     INTEGER NOT NULL DEFAULT 0
);"""


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(_DDL_TASKS)
    conn.execute(_DDL_REMINDERS)
    _migrate(conn)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after v1 without breaking existing databases."""
    existing = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
    for col, defn in [("due_time", "TEXT"), ("importance", "INTEGER"), ("event_type", "TEXT")]:
        if col not in existing:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {defn}")


# ── Normalizers ───────────────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()

def _norm_priority(p: str) -> str:
    p = p.lower()
    if p not in ("low", "medium", "high"):
        raise ValueError(f"Priority must be low/medium/high, got '{p}'")
    return p

def _norm_tags(tags) -> str:
    if isinstance(tags, list):
        tags = ",".join(tags)
    return ",".join(t.strip().lower() for t in str(tags).split(",") if t.strip())

def _norm_recurring(r) -> Optional[str]:
    if r is None or str(r).lower() in ("none", ""): return None
    r = r.lower()
    if r not in ("daily", "weekly", "monthly"):
        raise ValueError(f"Recurring must be daily/weekly/monthly, got '{r}'")
    return r

def _next_due(due: Optional[str], recurring: Optional[str]) -> Optional[str]:
    if not due or not recurring: return None
    d = date.fromisoformat(due)
    if recurring == "daily":   return (d + timedelta(days=1)).isoformat()
    if recurring == "weekly":  return (d + timedelta(weeks=1)).isoformat()
    if recurring == "monthly":
        m = d.month + 1
        y = d.year + (1 if m > 12 else 0)
        return d.replace(year=y, month=m % 12 or 12).isoformat()
    return None


# ── CRUD ──────────────────────────────────────────────────────────────────────

def add_task(title: str, due_date=None, due_time=None, priority: str = "medium",
             importance=None, event_type=None, tags="", recurring=None) -> int:
    priority  = _norm_priority(priority)
    tags      = _norm_tags(tags)
    recurring = _norm_recurring(recurring)
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title,due_date,due_time,priority,importance,event_type,"
            "tags,completed,created_at,recurring) VALUES (?,?,?,?,?,?,?,0,?,?)",
            (title, due_date, due_time, priority, importance, event_type, tags, _today(), recurring),
        )
        conn.commit()
        return cur.lastrowid

def complete_task(task_id: int) -> bool:
    with _db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row: return False
        conn.execute("UPDATE tasks SET completed=1 WHERE id=?", (task_id,))
        if row["recurring"] and not row["completed"]:
            nd = _next_due(row["due_date"], row["recurring"])
            conn.execute(
                "INSERT INTO tasks (title,due_date,due_time,priority,importance,event_type,"
                "tags,completed,created_at,recurring) VALUES (?,?,?,?,?,?,?,0,?,?)",
                (row["title"], nd, row["due_time"], row["priority"], row["importance"],
                 row["event_type"], row["tags"], _today(), row["recurring"]),
            )
        conn.commit()
    return True

def delete_task(task_id: int) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
        return cur.rowcount > 0

def edit_task(task_id: int, **kw) -> bool:
    allowed = {"title", "due_date", "due_time", "priority", "importance",
               "event_type", "tags", "recurring"}
    updates = {}
    for k, v in kw.items():
        if k not in allowed or v is None: continue
        if k == "priority":  v = _norm_priority(v)
        if k == "tags":      v = _norm_tags(v)
        if k == "recurring": v = _norm_recurring(v)
        updates[k] = v
    if not updates: return True
    sets = ", ".join(f"{k}=?" for k in updates)
    with _db() as conn:
        cur = conn.execute(f"UPDATE tasks SET {sets} WHERE id=?",
                           list(updates.values()) + [task_id])
        conn.commit()
        return cur.rowcount > 0

def get_tasks(completed=False, priority=None, tag=None, due_before=None):
    sql = "SELECT * FROM tasks WHERE completed=?"
    params = [1 if completed else 0]
    if priority:
        sql += " AND priority=?"; params.append(_norm_priority(priority))
    if tag:
        sql += " AND (',' || tags || ',') LIKE ?"; params.append(f"%,{tag.lower()},%")
    if due_before:
        sql += " AND due_date IS NOT NULL AND due_date <= ?"; params.append(due_before)
    sql += (" ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,"
            " due_date NULLS LAST")
    with _db() as conn:
        return conn.execute(sql, params).fetchall()

def get_overdue():
    return get_tasks(due_before=_today())


# ── Reminders ─────────────────────────────────────────────────────────────────

def add_reminder(task_id: int, notify_at: str, message: str = "") -> int:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (task_id,notify_at,message,fired) VALUES (?,?,?,0)",
            (task_id, notify_at, message),
        )
        conn.commit()
        return cur.lastrowid

def get_pending_reminders():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _db() as conn:
        return conn.execute(
            "SELECT r.*, t.title AS task_title FROM reminders r "
            "JOIN tasks t ON r.task_id=t.id "
            "WHERE r.fired=0 AND r.notify_at<=? ORDER BY r.notify_at",
            (now,),
        ).fetchall()

def mark_reminder_fired(rid: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE reminders SET fired=1 WHERE id=?", (rid,))
        conn.commit()

def get_task_reminders(task_id: int):
    with _db() as conn:
        return conn.execute(
            "SELECT * FROM reminders WHERE task_id=? ORDER BY notify_at",
            (task_id,),
        ).fetchall()


# ── Notifications ─────────────────────────────────────────────────────────────

def _send_notification(title: str, body: str) -> None:
    """macOS desktop notification + always echo to terminal."""
    try:
        safe_title = title.replace('"', "'")
        safe_body  = body.replace('"', "'")
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{safe_body}" with title "{safe_title}" sound name "Default"'],
            check=False, capture_output=True, timeout=3,
        )
    except Exception:
        pass
    print(f"\n  {RED_BOLD('🔔 REMINDER')}  {BOLD(title)}")
    print(f"     {body}")

def check_due_reminders() -> int:
    pending = get_pending_reminders()
    for r in pending:
        _send_notification("To-Do Reminder", r["message"] or r["task_title"])
        mark_reminder_fired(r["id"])
    return len(pending)


# ── Reminder timing helpers ───────────────────────────────────────────────────

_REMINDER_PRESETS = [
    ("1 week before",     timedelta(weeks=1)),
    ("2 days before",     timedelta(days=2)),
    ("1 day before",      timedelta(days=1)),
    ("3 hours before",    timedelta(hours=3)),
    ("1 hour before",     timedelta(hours=1)),
    ("30 minutes before", timedelta(minutes=30)),
    ("10 minutes before", timedelta(minutes=10)),
]

def parse_reminder_offset(text: str) -> Optional[timedelta]:
    """Convert '1 day before', '2 hours in advance', '45 minutes before' → timedelta."""
    patterns = [
        (r"(\d+)\s+weeks?\s+(?:before|in\s+advance)",  lambda n: timedelta(weeks=n)),
        (r"(\d+)\s+days?\s+(?:before|in\s+advance)",   lambda n: timedelta(days=n)),
        (r"(\d+)\s+hours?\s+(?:before|in\s+advance)",  lambda n: timedelta(hours=n)),
        (r"(\d+)\s+(?:mins?|minutes?)\s+(?:before|in\s+advance)", lambda n: timedelta(minutes=n)),
    ]
    text = text.lower().strip()
    for pat, fn in patterns:
        m = re.search(pat, text)
        if m: return fn(int(m.group(1)))
    return None

def _norm_time(raw: str) -> Optional[str]:
    """Normalize '2pm', '14:00', '2:30 PM' → 'HH:MM'."""
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", raw.strip(), re.I)
    if not m: return None
    h, mn = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3):
        suf = m.group(3).lower()
        if suf == "pm" and h < 12: h += 12
        elif suf == "am" and h == 12: h = 0
    return f"{h:02d}:{mn:02d}"

def compute_notify_at(due_date: Optional[str], due_time: Optional[str],
                      offset: timedelta) -> Optional[str]:
    """Return 'YYYY-MM-DD HH:MM' = (due datetime) − offset, or None."""
    if not due_date: return None
    time_str = due_time or "09:00"
    m = re.match(r"(\d{1,2}):(\d{2})", time_str)
    h, mn = (int(m.group(1)), int(m.group(2))) if m else (9, 0)
    try:
        y, mo, d = (int(x) for x in due_date.split("-"))
        notify_dt = datetime(y, mo, d, h, mn) - offset
        return notify_dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None


# ── Display ───────────────────────────────────────────────────────────────────

def _due_str(due: Optional[str], completed: bool) -> str:
    if not due: return ""
    if completed: return DIM(f"  due {due}")
    today = _today()
    if due < today:  return RED_BOLD(f"  OVERDUE ({due})")
    if due == today: return YELLOW("  due TODAY")
    delta = (date.fromisoformat(due) - date.today()).days
    if delta <= 3:   return YELLOW(f"  due {due} ({delta}d)")
    return DIM(f"  due {due}")

def _print_task(row: sqlite3.Row) -> None:
    done   = bool(row["completed"])
    pcolor = PRIORITY_COLOR.get(row["priority"], lambda t: t)
    title  = DIM(row["title"]) if done else row["title"]
    pri    = pcolor(f"[{row['priority'][:3].upper()}]")
    icon   = EVENT_ICONS.get(row["event_type"], "  ")
    imp    = MAGENTA(f"  ★{row['importance']}/10") if row["importance"] else ""
    tags   = ("  " + CYAN("·".join(row["tags"].split(",")))) if row["tags"] else ""
    recur  = f"  ↺{row['recurring']}" if row["recurring"] else ""
    done_m = DIM("  ✓") if done else ""
    id_s   = BOLD(f"{row['id']:>3}")
    print(f"  {id_s}  {icon}  {pri}  {title}"
          f"{_due_str(row['due_date'], done)}{imp}{tags}{recur}{done_m}")

def print_tasks(rows, header: str = "") -> None:
    if header: print(f"\n  {BOLD(header)}")
    if not rows: print("  (none)"); return
    print()
    for row in rows: _print_task(row)
    print()


# ── Natural-language parser (rule-based, zero deps) ───────────────────────────

_WEEKDAYS  = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
_MONTH_MAP = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
    "january":1,"february":2,"march":3,"april":4,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
}

def nl_parse_task(description: str) -> dict:
    """Parse plain-English task description — no API required."""
    today = date.today()
    text  = description

    # Tags
    tags: list[str] = []
    def _grab(m):
        tags.extend(p.lower() for p in re.split(r"[,\s]+", m.group(1).strip()) if p)
        return " "
    text = re.sub(
        r"\b(?:tag(?:ged)?|label(?:led)?)\s+(?:it\s+)?([a-z0-9_,\s]+?)"
        r"(?=\s*[,.]|\s+(?:and|by|on|at|due|every|daily|weekly|monthly"
        r"|urgent|asap|low|high|remind)|$)",
        _grab, text, flags=re.I,
    )
    text = re.sub(r"#([a-z0-9_]+)", lambda m: (tags.append(m.group(1).lower()), " ")[1],
                  text, flags=re.I)
    tags = list(dict.fromkeys(t.strip(".,") for t in tags if t.strip(".,'")))

    # Recurring — detect before date parsing so we can also set the anchor date
    recurring  = None
    due_date: Optional[str] = None   # declare early so weekday handler can set it

    # "every Monday/Friday/…" → weekly recurring, anchor = next that weekday
    for i, day in enumerate(_WEEKDAYS):
        m = re.search(rf"\bevery\s+{day}\b", text, re.I)
        if m:
            recurring = "weekly"
            ahead = (i - today.weekday()) % 7 or 7
            due_date = (today + timedelta(days=ahead)).isoformat()
            text = text[:m.start()] + text[m.end():]
            break

    if not recurring:
        for pat, val in [(r"\b(?:every\s+day|daily)\b","daily"),
                         (r"\b(?:every\s+week|weekly)\b","weekly"),
                         (r"\b(?:every\s+month|monthly)\b","monthly")]:
            if re.search(pat, text, re.I):
                recurring = val; text = re.sub(pat, " ", text, flags=re.I); break

    # Priority
    priority = "medium"
    if re.search(r"\b(?:urgent|asap|critical|high[\s-]priority|immediately)\b", text, re.I):
        priority = "high"
        text = re.sub(r"\b(?:urgent|asap|critical|high[\s-]priority|immediately)\b", " ", text, flags=re.I)
    elif re.search(r"\b(?:low[\s-]priority|whenever|not\s+urgent|someday|eventually)\b", text, re.I):
        priority = "low"
        text = re.sub(r"\b(?:low[\s-]priority|whenever|not\s+urgent|someday|eventually)\b", " ", text, flags=re.I)

    # Time
    due_time = None
    tm = re.search(r"\bat\s+(\d{1,2}(?::\d{2})?)\s*(am|pm)?\b", text, re.I)
    if tm:
        due_time = _norm_time(tm.group(0).replace("at ", "").strip()) or None
        text = text[:tm.start()] + text[tm.end():]

    # Date (due_date already declared above; set only if not already filled by recurring)
    def _try(d: date, pat: str) -> bool:
        nonlocal due_date, text
        if due_date: return False
        due_date = d.isoformat()
        text = re.sub(pat, " ", text, flags=re.I, count=1)
        return True

    for q in ("next", "this"):
        for i, day in enumerate(_WEEKDAYS):
            if re.search(rf"\b{q}\s+{day}\b", text, re.I):
                ahead = (i - today.weekday()) % 7
                if q == "next" and ahead == 0: ahead = 7
                _try(today + timedelta(days=ahead), rf"\b{q}\s+{day}\b"); break
        if due_date: break

    if not due_date:
        for i, day in enumerate(_WEEKDAYS):
            if re.search(rf"\b(?:on\s+)?{day}\b", text, re.I):
                _try(today + timedelta(days=(i - today.weekday()) % 7 or 7),
                     rf"\b(?:on\s+)?{day}\b"); break

    if not due_date and re.search(r"\btomorrow\b", text, re.I):
        _try(today + timedelta(days=1), r"\btomorrow\b")
    if not due_date and re.search(r"\btoday\b", text, re.I):
        _try(today, r"\btoday\b")

    if not due_date:
        m = re.search(r"\bin\s+(\d+)\s+(days?|weeks?|months?)\b", text, re.I)
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            if "month" in unit:
                mo = today.month + n; yr = today.year + (mo-1)//12; mo = (mo-1)%12+1
                d = today.replace(year=yr, month=mo)
            elif "week" in unit: d = today + timedelta(weeks=n)
            else:                d = today + timedelta(days=n)
            _try(d, r"\bin\s+\d+\s+(?:days?|weeks?|months?)\b")

    if not due_date:
        mp = "|".join(_MONTH_MAP)
        m = re.search(rf"\b({mp})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", text, re.I)
        if m:
            try:
                mo, dn = _MONTH_MAP[m.group(1).lower()], int(m.group(2))
                d = date(today.year, mo, dn)
                if d < today: d = date(today.year + 1, mo, dn)
                _try(d, rf"\b(?:{mp})\s+\d{{1,2}}(?:st|nd|rd|th)?\b")
            except ValueError: pass

    if not due_date:
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if m: due_date = m.group(1); text = text[:m.start()] + text[m.end():]

    for filler in [r"remind\s+me\s+to", r"don'?t\s+forget\s+to", r"remember\s+to",
                   r"i\s+need\s+to", r"i\s+have\s+to", r"i\s+must\b",
                   r"add\s+(?:a\s+)?task\s+to", r"todo[:\s]+", r"\bplease\b"]:
        text = re.sub(filler, " ", text, flags=re.I)

    title = re.sub(r"\s{2,}", " ", text).strip(" ,.")
    return {"title": title or description.strip(), "due_date": due_date,
            "due_time": due_time, "priority": priority, "tags": tags, "recurring": recurring}


# ── Menu helpers ──────────────────────────────────────────────────────────────

_W = 54  # menu width

def _hr(ch="─") -> str:
    return "  " + ch * _W

def _ask(prompt: str, default: str = "") -> str:
    try:
        v = input(prompt).strip()
        return v if v else default
    except (EOFError, KeyboardInterrupt):
        print(); return default

def _choose(options: list[str], prompt: str = "  Choice") -> Optional[int]:
    for i, o in enumerate(options, 1):
        print(f"    {BOLD(str(i))}.  {o}")
    raw = _ask(f"\n{prompt}: ")
    return int(raw) if raw.isdigit() and 1 <= int(raw) <= len(options) else None

def _banner() -> None:
    print()
    print(_hr("═"))
    print(f"  {BOLD('        TO-DO LIST MANAGER')}")
    print(_hr("═"))


# ── Reminder wizard (shared by Add Task and Add Event) ────────────────────────

def _reminder_wizard(task_id: int, due_date: Optional[str],
                      due_time: Optional[str], title: str) -> int:
    """Ask the user to add as many reminders as they like. Returns count added."""
    if not due_date:
        print(f"\n  {DIM('No due date set — reminders require a date. Skipping.')}")
        return 0

    added = 0
    date_str = due_date + (f" at {due_time}" if due_time else "")
    print(f"\n  {BOLD('── Reminders')}")
    print(f"  Event: {CYAN(title)}  on  {CYAN(date_str)}")
    print(f"  You can add as many reminders as you want.\n")

    while True:
        print(f"  When should we notify you?")
        labels = [label for label, _ in _REMINDER_PRESETS]
        opts   = labels + [
            f"Custom  {DIM('— e.g. \"2 days before\", \"45 minutes before\"')}",
            "Done — no more reminders",
        ]
        choice = _choose(opts, "  When")

        done_idx = len(_REMINDER_PRESETS) + 2
        custom_idx = len(_REMINDER_PRESETS) + 1

        if choice is None or choice == done_idx:
            break

        if choice == custom_idx:
            raw = _ask('  Enter offset (e.g. "2 days before", "45 minutes before"): ')
            offset = parse_reminder_offset(raw)
            if offset is None:
                print("  " + YELLOW("Couldn't parse that — try '2 days before' or '45 minutes before'."))
                continue
        else:
            offset = _REMINDER_PRESETS[choice - 1][1]

        notify_at = compute_notify_at(due_date, due_time, offset)
        if not notify_at:
            print(f"  {RED('Could not compute time.')}")
            continue
        if notify_at <= datetime.now().strftime("%Y-%m-%d %H:%M"):
            print(f"  {YELLOW(f'That time ({notify_at}) is already past — skipped.')}")
            continue

        msg = f"Upcoming: {title}" + (f" — {date_str}")
        add_reminder(task_id, notify_at, msg)
        added += 1
        print(f"  {GREEN('✓')} Reminder set for {CYAN(notify_at)}\n")

    if added:
        print(f"\n  {GREEN(str(added))} reminder(s) saved.")
    return added


# ── Menu: Add Task ────────────────────────────────────────────────────────────

def menu_add_task() -> None:
    print(f"\n{_hr()}")
    print(f"  {BOLD('ADD TASK')}")
    print(_hr())
    print(f"\n  Type your task in plain English.  Examples:")
    print(f"    {DIM('• \"submit report by Friday, high priority, tag it work\"')}")
    print(f"    {DIM('• \"call dentist tomorrow at 2pm, tag it health\"')}")
    print(f"    {DIM('• \"team standup every Monday, tag it work\"')}")
    print(f"    {DIM('• \"buy groceries, low priority, tag it errands\"')}")
    print()

    raw = _ask("  > ")
    if not raw: print("  Cancelled."); return

    p = nl_parse_task(raw)
    print(f"\n  {BOLD('Parsed:')}")
    print(f"    Title     : {p['title']}")
    print(f"    Due       : {p['due_date'] or '—'}  {p['due_time'] or ''}")
    print(f"    Priority  : {p['priority']}")
    print(f"    Tags      : {', '.join(p['tags']) or '—'}")
    print(f"    Recurring : {p['recurring'] or '—'}")

    if _ask("\n  Add this task? [Y/n]: ", "y").lower() not in ("y", "yes", ""):
        print("  Cancelled."); return

    tid = add_task(title=p["title"], due_date=p["due_date"], due_time=p["due_time"],
                   priority=p["priority"], tags=",".join(p["tags"]), recurring=p["recurring"])
    print(f"\n  {GREEN('✓')} Task #{tid} added: {BOLD(p['title'])}")
    _reminder_wizard(tid, p["due_date"], p["due_time"], p["title"])


# ── Menu: Add Event ───────────────────────────────────────────────────────────

_EVENT_TYPES = ["Birthday", "Meeting", "Deadline", "Holiday", "Other"]

def menu_add_event() -> None:
    print(f"\n{_hr()}")
    print(f"  {BOLD('ADD EVENT')}")
    print(_hr())
    print(f"\n  Events support importance ratings and multiple reminders.")
    print(f"  What kind of event?\n")
    choice = _choose(_EVENT_TYPES)
    if not choice: print("  Cancelled."); return

    event_type = _EVENT_TYPES[choice - 1].lower()
    icon = EVENT_ICONS.get(event_type, "📌")
    print(f"\n  {icon}  {BOLD(_EVENT_TYPES[choice - 1])}")

    title = _ask("  Event name: ")
    if not title: print("  Cancelled."); return

    print(f"\n  Date examples: \"next Friday\"  \"June 15\"  \"2026-12-25\"  \"in 10 days\"")
    due_raw = _ask("  Date: ")
    if not due_raw: print("  Cancelled."); return

    p = nl_parse_task(f"{title} {due_raw}")
    due_date = p.get("due_date")
    if not due_date:
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", due_raw)
        if m: due_date = m.group(1)

    if due_date: print(f"  Parsed date: {GREEN(due_date)}")
    else:        print(f"  {YELLOW('Date not recognised — saving without due date.')}")

    time_raw = _ask("  Time (e.g. \"14:00\" or \"2pm\", Enter to skip): ")
    due_time = _norm_time(time_raw) if time_raw else None
    if due_time: print(f"  Parsed time: {GREEN(due_time)}")

    imp_raw = _ask("  Importance 1–10 (Enter to skip): ")
    importance = int(imp_raw) if imp_raw.isdigit() and 1 <= int(imp_raw) <= 10 else None

    priority = ("high" if importance and importance >= 7
                else "low" if importance and importance <= 3
                else "medium")

    print(f"\n  {BOLD('Summary:')}")
    print(f"    {icon}  {title}")
    print(f"    Type        : {event_type}")
    print(f"    Date / Time : {due_date or '—'}  {due_time or ''}")
    print(f"    Importance  : {(str(importance) + '/10') if importance else '—'}  → priority: {priority}")

    if _ask("\n  Add this event? [Y/n]: ", "y").lower() not in ("y", "yes", ""):
        print("  Cancelled."); return

    tid = add_task(title=title, due_date=due_date, due_time=due_time,
                   priority=priority, importance=importance, event_type=event_type)
    print(f"\n  {GREEN('✓')} Event #{tid} added: {BOLD(title)}")
    _reminder_wizard(tid, due_date, due_time, title)


# ── Menu: View Tasks ──────────────────────────────────────────────────────────

def menu_view_tasks() -> None:
    print(f"\n{_hr()}")
    print(f"  {BOLD('VIEW TASKS')}")
    print(_hr())
    print()
    choice = _choose([
        "All open tasks",
        f"High-priority  {DIM('[urgent]')}",
        f"Overdue        {DIM('[past due date]')}",
        "Filter by tag",
        "Completed tasks",
    ])
    if choice == 1: print_tasks(get_tasks(), "All open tasks")
    elif choice == 2: print_tasks(get_tasks(priority="high"), "High-priority tasks")
    elif choice == 3: print_tasks(get_overdue(), "Overdue tasks")
    elif choice == 4:
        tag = _ask("  Tag name: ")
        if tag: print_tasks(get_tasks(tag=tag), f"Tasks tagged '{tag}'")
    elif choice == 5: print_tasks(get_tasks(completed=True), "Completed tasks")


# ── Menu: Delete Task ─────────────────────────────────────────────────────────

def menu_delete_task() -> None:
    print(f"\n{_hr()}")
    print(f"  {BOLD('DELETE TASK')}")
    print(_hr())
    print_tasks(get_tasks(), "Open tasks")

    raw = _ask("  Task ID to delete (Enter to cancel): ")
    if not raw or not raw.isdigit(): print("  Cancelled."); return

    tid = int(raw)
    if _ask(f"  Delete task #{tid}? [y/N]: ", "n").lower() not in ("y", "yes"):
        print("  Cancelled."); return

    if delete_task(tid): print(f"  {GREEN('✓')} Task #{tid} deleted.")
    else:                print(f"  {RED(f'Task #{tid} not found.')}")


# ── Main interactive menu ─────────────────────────────────────────────────────

def run_menu() -> None:
    while True:
        _banner()

        fired = check_due_reminders()
        if fired:
            print(f"\n  {YELLOW(f'⚑  {fired} reminder(s) just fired — check above.')}")

        open_t   = get_tasks()
        overdue_ = get_overdue()
        if open_t:
            stat = f"  {len(open_t)} open task(s)"
            if overdue_: stat += f"  {RED_BOLD(f'· {len(overdue_)} overdue')}"
            print(f"\n  {DIM(stat)}")

        print()
        choice = _choose([
            f"Add Task    {DIM('— e.g. \"call dentist tomorrow at 2pm, tag it health\"')}",
            f"Add Event   {DIM('— birthdays, meetings, deadlines + importance 1–10 + reminders')}",
            f"View Tasks  {DIM('— browse, filter by priority / tag / overdue')}",
            f"Delete Task {DIM('— remove a task by ID')}",
            f"Quit",
        ])
        print()

        if   choice == 1: menu_add_task()
        elif choice == 2: menu_add_event()
        elif choice == 3: menu_view_tasks()
        elif choice == 4: menu_delete_task()
        elif choice == 5: print("  Bye!"); break
        else:
            print(f"  {DIM('Please enter a number 1–5.')}")
            continue

        if choice in (1, 2, 3, 4):
            _ask(f"\n  {DIM('Press Enter to return to menu...')}")


# ── Direct CLI (for scripts / power users) ────────────────────────────────────

def cmd_add(args) -> None:
    if args.ai:
        query = " ".join(args.ai) if isinstance(args.ai, list) else args.ai
        print(f"  Parsing: {query!r}")
        p = nl_parse_task(query)
        title, due, due_time = p["title"], p["due_date"], p.get("due_time")
        priority, tags, recurring = p["priority"], ",".join(p["tags"]), p["recurring"]
        print(f"  → title={title!r}  due={due}  {due_time or ''}  "
              f"priority={priority}  tags={tags!r}  recurring={recurring}")
    else:
        if not args.title: print("  Provide a title or use --ai"); sys.exit(1)
        title     = " ".join(args.title) if isinstance(args.title, list) else args.title
        due       = args.due
        due_time  = getattr(args, "time", None)
        priority  = args.priority or "medium"
        tags      = args.tags or ""
        recurring = args.recurring

    tid = add_task(title, due, due_time, priority, None, None, tags, recurring)
    print(f"  Added task #{tid}: {title!r}")

def cmd_list(args) -> None:
    label = "Open tasks"
    if args.priority: label += f" [{args.priority}]"
    if args.tag:      label += f" #{args.tag}"
    print_tasks(get_tasks(priority=args.priority, tag=args.tag), label)

def cmd_done_list(_args)  -> None: print_tasks(get_tasks(completed=True), "Completed tasks")
def cmd_overdue(_args)    -> None: print_tasks(get_overdue(), "Overdue tasks")
def cmd_done(args)        -> None:
    print(f"  Task #{args.id} marked complete." if complete_task(args.id)
          else f"  Task #{args.id} not found.")
def cmd_delete(args)      -> None:
    print(f"  Task #{args.id} deleted." if delete_task(args.id)
          else f"  Task #{args.id} not found.")

def cmd_edit(args) -> None:
    kw = {k: v for k, v in vars(args).items()
          if k in ("title","due","priority","tags","recurring") and v is not None}
    if "due" in kw: kw["due_date"] = kw.pop("due")
    if "title" in kw and isinstance(kw["title"], list): kw["title"] = " ".join(kw["title"])
    print(f"  Task #{args.id} updated." if edit_task(args.id, **kw)
          else f"  Task #{args.id} not found.")


def build_parser() -> argparse.ArgumentParser:
    ap  = argparse.ArgumentParser(description="To-Do List Manager")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("add")
    p.add_argument("title", nargs="*")
    p.add_argument("--ai",       nargs="*", metavar="QUERY",
                   help="Natural-language description (no API key needed)")
    p.add_argument("--due",      metavar="YYYY-MM-DD")
    p.add_argument("--time",     metavar="HH:MM")
    p.add_argument("--priority", choices=["low","medium","high"])
    p.add_argument("--tags",     metavar="tag1,tag2")
    p.add_argument("--recurring",choices=["daily","weekly","monthly"])

    p = sub.add_parser("list")
    p.add_argument("--priority", choices=["low","medium","high"])
    p.add_argument("--tag",      metavar="TAG")

    sub.add_parser("completed")
    sub.add_parser("overdue")

    p = sub.add_parser("done");   p.add_argument("id", type=int)
    p = sub.add_parser("delete"); p.add_argument("id", type=int)

    p = sub.add_parser("edit");   p.add_argument("id", type=int)
    p.add_argument("--title",    nargs="*")
    p.add_argument("--due",      metavar="YYYY-MM-DD")
    p.add_argument("--priority", choices=["low","medium","high"])
    p.add_argument("--tags",     metavar="tag1,tag2")
    p.add_argument("--recurring",choices=["daily","weekly","monthly","none"])

    return ap


def main() -> None:
    ap    = build_parser()
    args  = ap.parse_args()
    dispatch = {
        "add": cmd_add, "list": cmd_list, "completed": cmd_done_list,
        "overdue": cmd_overdue, "done": cmd_done, "delete": cmd_delete, "edit": cmd_edit,
    }
    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        run_menu()


if __name__ == "__main__":
    main()
