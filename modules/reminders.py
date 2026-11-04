# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Hatırlatıcı
-----------
"yarın 15:00'te toplantıyı hatırlat", "20 dakika sonra çayı hatırlat" gibi istekler.
Hatırlatmalar SQLite'ta (fenix_memory.db) tutulur; FENIX kapalıyken zamanı gelenler bir sonraki
açılışta "kaçırılan hatırlatma" olarak gösterilir.
"""
import re
import datetime

WEEKDAYS = {"pazartesi": 0, "salı": 1, "sali": 1, "çarşamba": 2, "carsamba": 2, "perşembe": 3, "persembe": 3,
            "cuma": 4, "cumartesi": 5, "pazar": 6}


def _norm(t):
    return (t or "").lower().replace("’", "'").strip()


def parse_when(text, now=None):
    """Türkçe ya da ISO zaman ifadesini datetime'a çevirir. Anlaşılamazsa None.
    Örnekler: '2026-10-10 15:00', '15:30', '20 dakika sonra', '1 saat 15 dakika sonra', 'yarın 9:00',
    'yarın sabah', 'bugün akşam 8', 'cuma 14:00', 'saat 3'te', 'öbür gün 10'."""
    now = (now or datetime.datetime.now()).replace(microsecond=0)
    t = _norm(text)
    if not t:
        return None
    # ISO / tam tarih
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.datetime.strptime(t[:19] if "t" in fmt.lower() and "T" in text else t, fmt)
        except ValueError:
            pass
    try:
        return datetime.datetime.fromisoformat(text.strip()).replace(tzinfo=None)
    except ValueError:
        pass

    # Göreli: "1 saat 30 dakika sonra", "45 dk sonra", "yarım saat sonra"
    t2 = t.replace("yarım saat", "30 dakika").replace("bir buçuk saat", "90 dakika").replace("çeyrek saat", "15 dakika")
    t2 = re.sub(r"\bbir\b", "1", t2)
    rel = re.findall(r"(\d+)\s*(saniye|sn|dakika|dakka|dk|saat|sa|gün|gun|hafta)", t2)
    if rel and ("sonra" in t2 or "içinde" in t2 or "icinde" in t2 or re.fullmatch(r"[\d\s\w]*", t2)):
        delta = datetime.timedelta()
        for n, unit in rel:
            n = int(n)
            if unit in ("saniye", "sn"):
                delta += datetime.timedelta(seconds=n)
            elif unit in ("dakika", "dakka", "dk"):
                delta += datetime.timedelta(minutes=n)
            elif unit in ("saat", "sa"):
                delta += datetime.timedelta(hours=n)
            elif unit in ("gün", "gun"):
                delta += datetime.timedelta(days=n)
            else:
                delta += datetime.timedelta(weeks=n)
        if delta.total_seconds() > 0 and ("sonra" in t2 or "içinde" in t2 or "icinde" in t2):
            return now + delta

    # Gün
    day = now.date()
    explicit_day = False
    if "öbür gün" in t or "obur gun" in t or "ertesi gün" in t:
        day, explicit_day = day + datetime.timedelta(days=2 if "öbür" in t or "obur" in t else 1), True
    elif "yarın" in t or "yarin" in t:
        day, explicit_day = day + datetime.timedelta(days=1), True
    elif "bugün" in t or "bugun" in t:
        explicit_day = True
    else:
        for name, wd in WEEKDAYS.items():
            if re.search(rf"\b{name}\b", t):
                ahead = (wd - now.weekday()) % 7 or 7
                day, explicit_day = day + datetime.timedelta(days=ahead), True
                break

    # Saat
    hour = minute = None
    bare_hour = False          # "saat 3'te" gibi dakikasız saat (öğleden sonra olabilir)
    m = re.search(r"(\d{1,2})[:.](\d{2})", t)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
    else:
        m = re.search(r"saat\s*(\d{1,2})|(\d{1,2})\s*'?\s*(?:de|da|te|ta|'de|'da|'te|'ta)\b|\b(\d{1,2})\s*$", t)
        if m:
            hour, minute = int(next(g for g in m.groups() if g)), 0
            bare_hour = True
    part = None
    for word, default_h, pm in (("sabah", 9, False), ("öğle", 12, False), ("ogle", 12, False),
                                ("akşam", 19, True), ("aksam", 19, True), ("gece", 22, True)):
        if word in t:
            part = (default_h, pm)
            break
    if hour is None and part:
        hour, minute = part[0], 0
    elif hour is not None and part and part[1] and hour < 12:
        hour += 12
    if hour is None:
        if explicit_day:
            hour, minute = 9, 0
        else:
            return None
    if not (0 <= hour <= 23 and 0 <= (minute or 0) <= 59):
        return None
    when = datetime.datetime.combine(day, datetime.time(hour, minute or 0))
    if when <= now:
        if not explicit_day:
            # "saat 3'te" -> önce bugün 15:00'e bak, o da geçtiyse yarın
            if bare_hour and hour < 12 and part is None and when.replace(hour=hour + 12) > now:
                return when.replace(hour=hour + 12)
            return when + datetime.timedelta(days=1)
        if day == now.date():
            return None
    return when


class ReminderStore:
    def __init__(self, conn):
        self.conn = conn
        self.conn.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, due TEXT, text TEXT,
            done INTEGER DEFAULT 0, session_id INTEGER)""")
        self.conn.commit()

    def add(self, due, text, session_id=None):
        return self.conn.insert("INSERT INTO reminders (created, due, text, done, session_id) VALUES (?,?,?,0,?)",
                                (datetime.datetime.now().isoformat(timespec="seconds"),
                                 due.isoformat(timespec="seconds"), text.strip(), session_id))

    def pending(self):
        rows = self.conn.execute("SELECT id, due, text FROM reminders WHERE done=0 ORDER BY due").fetchall()
        return [{"id": r[0], "due": datetime.datetime.fromisoformat(r[1]), "text": r[2]} for r in rows]

    def due_now(self, now=None):
        now = now or datetime.datetime.now()
        return [r for r in self.pending() if r["due"] <= now]

    def mark_done(self, rid):
        self.conn.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))
        self.conn.commit()

    def snooze(self, rid, minutes=10):
        due = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds")
        self.conn.execute("UPDATE reminders SET due=?, done=0 WHERE id=?", (due, rid))
        self.conn.commit()

    def cancel(self, rid):
        r = self.conn.execute("SELECT id FROM reminders WHERE id=? AND done=0", (rid,)).fetchone()
        if not r:
            return False
        self.conn.execute("UPDATE reminders SET done=2 WHERE id=?", (rid,))
        self.conn.commit()
        return True


def human_when(due, now=None):
    now = now or datetime.datetime.now()
    d = (due.date() - now.date()).days
    day = "bugün" if d == 0 else "yarın" if d == 1 else due.strftime("%d.%m.%Y")
    return f"{day} {due:%H:%M}"
