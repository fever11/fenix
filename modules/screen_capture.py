# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Gözler: Olay bazlı tek kare ekran yakalama. Sürekli bellekte tutulmaz,
yakalanır, base64'e çevrilir, çağıran taraf işi bitince referansı bırakır."""
import io
import base64
import mss
from PIL import Image


def capture_screen_base64(max_size=(1280, 1280), quality=70, monitor_index=1):
    with mss.mss() as sct:
        monitors = sct.monitors
        idx = monitor_index if monitor_index < len(monitors) else 1
        shot = sct.grab(monitors[idx])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img.thumbnail(max_size)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
