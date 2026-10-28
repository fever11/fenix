# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Ekran Etkileşimi (Spotlight)
----------------------------
Masaüstünü kapatmadan, ekranın belirli bir bölgesini yarı saydam, tıklama
geçirgen (click-through) bir katmanla parlak çerçeve veya daire ile işaretler.
FENIX "şurada" derken ekranda gösterebilsin diye.

Kullanım:
    from modules.spotlight import Spotlight
    sp = Spotlight()
    sp.highlight_rect(x, y, w, h, duration=3)     # dikdörtgen çerçeve
    sp.highlight_circle(cx, cy, r, duration=3)    # daire
Koordinatlar ekran pikseli. duration saniye sonunda otomatik kapanır.
"""
import tkinter as tk
import threading

_NEON = "#10b981"  # zümrüt


class Spotlight:
    def _show(self, draw_fn, duration):
        def run():
            root = tk.Tk()
            root.attributes("-fullscreen", True)
            root.attributes("-topmost", True)
            # Siyahı şeffaf yap (Windows): sadece çizdiğimiz çizgiler görünür
            trans_color = "#000001"
            root.configure(bg=trans_color)
            try:
                root.attributes("-transparentcolor", trans_color)
            except Exception:
                root.attributes("-alpha", 0.35)
            root.overrideredirect(True)

            w = root.winfo_screenwidth()
            h = root.winfo_screenheight()
            canvas = tk.Canvas(root, width=w, height=h, bg=trans_color, highlightthickness=0)
            canvas.pack()
            draw_fn(canvas)

            # Tıklama geçirgenliği (mümkünse): pencere fareyi engellemesin
            try:
                root.wm_attributes("-disabled", True)
            except Exception:
                pass

            root.after(int(duration * 1000), root.destroy)
            root.mainloop()

        threading.Thread(target=run, daemon=True).start()

    def highlight_rect(self, x, y, w, h, duration=3, color=_NEON, width=5):
        def draw(c):
            for i in range(width):
                c.create_rectangle(x - i, y - i, x + w + i, y + h + i, outline=color)
        self._show(draw, duration)

    def highlight_circle(self, cx, cy, r, duration=3, color=_NEON, width=5):
        def draw(c):
            for i in range(width):
                c.create_oval(cx - r - i, cy - r - i, cx + r + i, cy + r + i, outline=color)
        self._show(draw, duration)

    def highlight_arrow(self, x, y, duration=3, color=_NEON):
        """Bir noktayı ok + daire ile işaretler."""
        def draw(c):
            c.create_oval(x - 30, y - 30, x + 30, y + 30, outline=color, width=4)
            c.create_line(x - 90, y - 90, x - 20, y - 20, fill=color, width=5, arrow=tk.LAST)
        self._show(draw, duration)
