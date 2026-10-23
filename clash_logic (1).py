"""Rule-based timetable clash detection (no AI needed for correctness)."""
import pandas as pd

REQUIRED = ["day", "start", "end", "subject", "faculty", "room", "class_group"]
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
CLASH_RULES = {"room": "Room double-booked",
               "faculty": "Faculty in two places",
               "class_group": "Class has two sessions"}


def to_minutes(t: str) -> int:
    h, m = str(t).strip().split(":")
    return int(h) * 60 + int(m)


def to_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def load_timetable(source) -> pd.DataFrame:
    """Read CSV/Excel (path or uploaded file), validate, add minute columns."""
    name = getattr(source, "name", str(source)).lower()
    df = pd.read_excel(source) if name.endswith((".xlsx", ".xls")) else pd.read_csv(source)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    for c in ["day", "subject", "faculty", "room", "class_group"]:
        df[c] = df[c].astype(str).str.strip()
    df["start_min"] = df["start"].map(to_minutes)
    df["end_min"] = df["end"].map(to_minutes)
    bad = df[df["end_min"] <= df["start_min"]]
    if not bad.empty:
        raise ValueError(f"End time must be after start time (rows: {list(bad.index + 2)})")
    return df.reset_index(drop=True)


def overlaps(s1: int, e1: int, s2: int, e2: int) -> bool:
    return s1 < e2 and s2 < e1


def find_clashes(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per clash between two sessions on the same day."""
    rows = []
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            a, b = df.iloc[i], df.iloc[j]
            if a["day"] != b["day"]:
                continue
            if not overlaps(a.start_min, a.end_min, b.start_min, b.end_min):
                continue
            for col, label in CLASH_RULES.items():
                if a[col].lower() == b[col].lower():
                    rows.append({
                        "type": label, "day": a["day"], "shared": a[col],
                        "session_1": f"{a.subject} ({a.start}-{a.end})",
                        "session_2": f"{b.subject} ({b.start}-{b.end})",
                        "row_1": i, "row_2": j,
                    })
    return pd.DataFrame(rows, columns=["type", "day", "shared", "session_1",
                                       "session_2", "row_1", "row_2"])


def free_slots(df, column, value, day, day_start=540, day_end=1020, min_len=60):
    """Free gaps (>= min_len minutes) for a room/faculty/class on a day."""
    busy = df[(df["day"] == day) & (df[column].str.lower() == value.lower())]
    busy = sorted(zip(busy.start_min, busy.end_min))
    gaps, cursor = [], day_start
    for s, e in busy:
        if s - cursor >= min_len:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if day_end - cursor >= min_len:
        gaps.append((cursor, day_end))
    return [f"{to_hhmm(s)}-{to_hhmm(e)}" for s, e in gaps]


def free_rooms(df, day, start_min, end_min):
    """Known rooms with no session overlapping the given interval."""
    free = []
    for room in sorted(df["room"].unique()):
        r = df[(df["day"] == day) & (df["room"] == room)]
        if not any(overlaps(start_min, end_min, s, e) for s, e in zip(r.start_min, r.end_min)):
            free.append(room)
    return free


def suggest_fix(df, clash) -> str:
    """Suggestion for the second session in a clash."""
    b = df.iloc[clash["row_2"]]
    if clash["type"] == "Room double-booked":
        rooms = free_rooms(df, b.day, b.start_min, b.end_min)
        return ("Move to free room: " + ", ".join(rooms)) if rooms else "No free room at this time"
    col = "faculty" if clash["type"] == "Faculty in two places" else "class_group"
    slots = free_slots(df, col, b[col], b.day, min_len=b.end_min - b.start_min)
    return ("Free slots that day: " + ", ".join(slots)) if slots else "No free slot that day"


def explain_clash(df, clash) -> str:
    """Plain-English, rule-based explanation of one clash."""
    a, b = df.iloc[clash["row_1"]], df.iloc[clash["row_2"]]
    lo, hi = max(a.start_min, b.start_min), min(a.end_min, b.end_min)
    when = f"{to_hhmm(lo)}-{to_hhmm(hi)}"
    if clash["type"] == "Room double-booked":
        why = f"- both use room {a.room}"
    elif clash["type"] == "Faculty in two places":
        why = f"- {a.faculty} is scheduled for both"
    else:
        why = f"- class {a.class_group} is scheduled for both"
    return (f"On {a.day}, {a.subject} ({a.start}-{a.end}) and {b.subject} "
            f"({b.start}-{b.end}) {why}, overlapping for {when}.")


def weekly_grid(df, clash_rows, day_start=540, day_end=1020, step=60):
    """Weekly grid: rows = time slots, columns = days.
    Returns (text grid, boolean grid marking cells that contain a clash)."""
    days = [d for d in DAY_ORDER if d in set(df["day"])] or sorted(df["day"].unique())
    labels, text, flag = [], [], []
    for s in range(day_start, day_end, step):
        e = s + step
        labels.append(f"{to_hhmm(s)}-{to_hhmm(e)}")
        trow, frow = [], []
        for d in days:
            hits = df[(df["day"] == d) &
                      df.apply(lambda r: overlaps(s, e, r.start_min, r.end_min), axis=1)]
            trow.append(" | ".join(f"{r.subject} ({r.room}, {r.class_group})"
                                   for r in hits.itertuples()))
            frow.append(any(i in clash_rows for i in hits.index))
        text.append(trow)
        flag.append(frow)
    return (pd.DataFrame(text, index=labels, columns=days),
            pd.DataFrame(flag, index=labels, columns=days))
