# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Kişisel İstatistik & Telemetri
------------------------------
Hafif ölçüm: oturum süresi, aktif pencere kategorisi (kodlama/araştırma/oyun),
ve anlık CPU/RAM. Veriler SQLite'a stream edilir (bellekte biriktirilmez).

Kategori eşlemesi basit tutuldu; aktif pencere başlığına göre tahmin eder.
"""
import time
import threading
import datetime

try:
    import psutil
except Exception:
    psutil = None


CATEGORY_HINTS = {
    "kodlama": ["visual studio", "vscode", "code", "pycharm", "sublime", "intellij", "terminal", "powershell", "cmd"],
    "araştırma": ["chrome", "firefox", "edge", "opera", "wikipedia", "docs", "stack"],
    "oyun": ["steam", "epic", "forza", "game", "riot", "valorant", "minecraft"],
    "medya": ["youtube", "netflix", "spotify", "vlc"],
}


def _active_window_title():
    try:
        import pygetwindow as gw
        w = gw.getActiveWindow()
        return (w.title if w else "") or ""
    except Exception:
        return ""


def categorize(title):
    t = title.lower()
    for cat, hints in CATEGORY_HINTS.items():
        if any(h in t for h in hints):
            return cat
    return "diğer"


class StatsTracker:
    def __init__(self, memory=None, sample_interval=15):
        self.memory = memory
        self.interval = sample_interval
        self.session_start = time.time()
        self._running = False
        self._category_seconds = {}
        self._last_activity = time.time()

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            title = _active_window_title()
            cat = categorize(title)
            self._category_seconds[cat] = self._category_seconds.get(cat, 0) + self.interval
            if self.memory:
                try:
                    self.memory.log_event("activity", f"{cat}|{title[:60]}")
                except Exception:
                    pass
            time.sleep(self.interval)

    def session_minutes(self):
        return round((time.time() - self.session_start) / 60, 1)

    def category_breakdown(self):
        return dict(sorted(self._category_seconds.items(), key=lambda x: -x[1]))

    def system_load(self):
        if not psutil:
            return {"cpu": "?", "ram_mb": "?"}
        try:
            proc = psutil.Process()
            return {
                "cpu": f"{psutil.cpu_percent():.0f}%",
                "ram_mb": f"{proc.memory_info().rss / 1024 / 1024:.0f}",
                "ram_total": f"{psutil.virtual_memory().percent:.0f}%",
            }
        except Exception:
            return {"cpu": "?", "ram_mb": "?"}
