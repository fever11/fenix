# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
FENIX - Masaüstü arayüz / desktop UI (CustomTkinter)
=============================================
4 bölmeli yerleşim:
  Sol        : Mod seçimi + menü (İstatistikler, Geçmiş, Yetenekler, Ayarlar -> ayrı pencereler)
  İç sol     : Canlı görev pipeline'ı (adım listesi + ilerleme + süre)
  Merkez     : Reaktif neon küre + mikrofon butonu
  Sağ        : Chat konsolu + onay kutuları

Çalıştırma: python app.py   (veya Start_FENIX.vbs ile sessiz)
"""
import os
import re
import gc
import math
import time
import queue
import threading
import datetime

import json
import yaml
import customtkinter as ctk

from modules.audio_io import PushToTalkRecorder, speak, stop_speaking, is_speaking, list_input_devices, MicError
from modules import stt
from modules.memory import Memory
from modules.llm_client import LLMClient, GorevIptal
from modules.killswitch import KillSwitch
from modules.agent import Agent
from modules import functions as fx
from modules.stats import StatsTracker
from modules.spotlight import Spotlight
from modules.reports import ReportStore, human_size
from modules.reminders import ReminderStore, parse_when, human_when
from modules import macros as macro_store
from modules import user_settings
from modules import audio_io
from modules import attachments as att
from modules import notifier
from modules import command_memory as cmem
from modules import pc_tools
from modules import nobet
from modules.version import VERSION as FENIX_VERSION
from modules import i18n
from modules import imza
try:                                   # özel sürüm: öğrenme modu (paylaşılan pakette bu modül yoktur)
    from modules import ogrenme as OGR
    OGR.install()
except ImportError:
    OGR = None
from modules import mcp_eklenti as MCPX     # eklentiler (MCP); 'mcp' paketi yoksa kendiliğinden kapalı kalır
from modules import yol_hafizasi as YOLH     # yol hafızası: benzer işlerde izlenen yolu hatırlar
from modules import fenix_bilgi as FBILGI   # kendini tanı: FENIX kendisi hakkında gerçek bilgileri buradan okur
MCPX.install()

try:                                   # sürükle-bırak (pip install tkinterdnd2); yoksa sadece 📎 butonu
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_BASES = (TkinterDnD.DnDWrapper,)
except Exception:
    TkinterDnD, DND_FILES, _DND_BASES = None, None, ()

# --- Renk paleti (holografik tema) ---
BG = "#04070d"
PANEL = "#060c16"
PANEL2 = "#0b1522"
LINE = "#16324a"            # ince çerçeve / ayraç çizgileri
GRID = "#0a1825"            # merkezdeki ızgara
EMERALD = "#38bdf8"
CYAN = "#7dd3fc"
AMBER = "#fbbf24"
TEXT = "#dbe7f3"
MUTED = "#8aa0b6"
FONT_HEAD = "Bahnschrift"   # Windows 10/11'de hazır gelen teknik görünümlü yazı tipi (yoksa varsayılana düşer)
FONT_MONO = "Consolas"

# Mod renkleri: canlı mod göstergeleri (küre, pipeline, mod butonu, FENIX yazısı) moda göre değişir.
# Güvenli = mavi (sakin/salt-okunur), Normal = yeşil (şimdiki hâl), Devil = kırmızı (tam yetki, dikkat).
MODE_ACCENT = {
    "safe":   {"base": "#818cf8", "light": "#a5b4fc", "hover": "#6366f1"},
    "normal": {"base": "#38bdf8", "light": "#7dd3fc", "hover": "#0ea5e9"},
    "devil":  {"base": "#f87171", "light": "#fca5a5", "hover": "#ef4444"},
}
if OGR:
    MODE_ACCENT.update(OGR.MODE_ACCENT)
MODE_KEYS = ("safe", "normal", "devil") + ((OGR.MODE_KEY,) if OGR else ())

_THEME = {"base": EMERALD, "hover": CYAN}      # yan pencereler açılırken o anki modun rengini alır

ctk.set_appearance_mode("dark")
# Holografik tema: keskin köşeler, ince çerçeveler (tüm pencerelerdeki varsayılanlar)
try:
    _T = ctk.ThemeManager.theme
    for _w, _r in (("CTkButton", 4), ("CTkEntry", 4), ("CTkTextbox", 4), ("CTkSegmentedButton", 4),
                   ("CTkOptionMenu", 4), ("CTkComboBox", 4), ("CTkFrame", 6)):
        if _w in _T:
            _T[_w]["corner_radius"] = _r
    _T["CTkButton"]["border_width"] = 1
    _T["CTkButton"]["border_color"] = ["#16324a", "#16324a"]
    _T["CTkEntry"]["border_color"] = ["#16324a", "#16324a"]
    _T["CTkTextbox"]["border_width"] = 1
    _T["CTkTextbox"]["border_color"] = ["#16324a", "#16324a"]
except Exception as _e:
    print(f"[TEMA] {_e}")


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def mask_key(key):
    """API anahtarını ekranda tam göstermemek için maskeler."""
    key = (key or "").strip()
    if not key or key.startswith("BURAYA"):
        return "girilmemiş"
    if len(key) <= 10:
        return "girilmiş"
    return f"{key[:4]}…{key[-4:]}  (girilmiş)"


# =====================================================================
#  AYRI PENCERELER
# =====================================================================
class ReadOnlyWindow(ctk.CTkToplevel):
    """Salt okunur bilgi penceresi. refresh_fn verilirse her interval_ms'de yenilenir."""

    def __init__(self, app, title, text_fn, interval_ms=0, size="520x560"):
        super().__init__(app)
        self.app = app
        self.text_fn = text_fn
        self.interval_ms = interval_ms
        self._alive = True
        self.title(f"FENIX • {title}")
        self.geometry(size)
        self.configure(fg_color=BG)
        self.minsize(380, 320)

        self.box = ctk.CTkTextbox(self, fg_color=PANEL2, text_color=TEXT, font=("Consolas", 12), wrap="word")
        self.box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(bar, text="Salt okunur", text_color=MUTED, font=("Segoe UI", 10)).pack(side="left")
        ctk.CTkButton(bar, text="Kapat", width=80, fg_color=PANEL, hover_color=CYAN,
                      command=self.close).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def _open_session(self, sid):
        self.app._open_session(sid)
        self.app.lift()

    def refresh(self):
        if not self._alive:
            return
        try:
            text = self.text_fn()
        except Exception as e:
            text = f"(Veri alınamadı: {e})"
        # Kullanıcı kaydırmışsa yenileme kaydırmayı bozmasın
        top = self.box.yview()[0]
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.insert("1.0", text)
        self.box.configure(state="disabled")
        self.box.yview_moveto(top)
        if self.interval_ms:
            self.after(self.interval_ms, self.refresh)

    def close(self):
        self._alive = False
        self.destroy()


class SettingsWindow(ReadOnlyWindow):
    """⚙️ Ayarlar: üstte dil seçimi, altta ayarların salt okunur özeti."""

    def __init__(self, app, text_fn):
        super().__init__(app, "Ayarlar", text_fn, size="560x680")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(10, 0), before=self.box)
        ctk.CTkLabel(row, text="🌐 Dil / Language:", text_color=TEXT, font=("Segoe UI", 12)).pack(side="left")
        self._codes = list(i18n.LANGS.keys())
        names = [i18n.LANGS[c] for c in self._codes]
        self.lang_menu = ctk.CTkOptionMenu(row, values=names, command=self._on_lang, width=160,
                                           fg_color=PANEL2, button_color=PANEL, button_hover_color=CYAN)
        self.lang_menu.set(i18n.LANGS[i18n.lang()])
        self.lang_menu.pack(side="left", padx=(8, 0))
        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(8, 0), before=self.box)
        self.sw_yol = ctk.CTkSwitch(row2, text="🧭 Yol hafızası (benzer işleri daha hızlı yapar)",
                                    command=lambda: user_settings.set("yol_hafizasi", bool(self.sw_yol.get())),
                                    font=("Segoe UI", 12), text_color=TEXT)
        if user_settings.get("yol_hafizasi", True):
            self.sw_yol.select()
        self.sw_yol.pack(anchor="w")
        self.sw_bildirim = ctk.CTkSwitch(row2, text="🔔 Başka penceredeyken cevap gelince bildirim göster",
                                         command=lambda: user_settings.set("cevap_bildirimi",
                                                                           bool(self.sw_bildirim.get())),
                                         font=("Segoe UI", 12), text_color=TEXT)
        if user_settings.get("cevap_bildirimi", True):
            self.sw_bildirim.select()
        self.sw_bildirim.pack(anchor="w", pady=(6, 0))

    def _on_lang(self, name):
        code = self._codes[[i18n.LANGS[c] for c in self._codes].index(name)]
        if code == i18n.lang():
            return
        i18n.save_language(code)
        from tkinter import messagebox
        messagebox.showinfo("FENIX", "Dil kaydedildi. Değişikliğin uygulanması için FENIX'i yeniden başlat.\n\n"
                                     "Language saved. Restart FENIX to apply it.", parent=self)


class PluginsWindow(ctk.CTkToplevel):
    """🧩 Eklentiler (MCP): aç/kapat, anahtar gir, Uygula. config.yaml'ı elle düzenlemek gerekmez."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._alive = True
        self.title("FENIX • Eklentiler")
        self.geometry("680x640")
        self.minsize(520, 420)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close)
        ctk.CTkLabel(self, text="Eklentiler (MCP)", text_color=TEXT, font=(FONT_HEAD, 16)).pack(
            anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(self, text="Açmak istediğin eklentiyi işaretle, gerekiyorsa anahtarını yapıştır ve Uygula'ya bas. "
                                "Yazma/silme yapan her eklenti işlemi yine onay kutusuyla sorulur.",
                     text_color=MUTED, font=("Segoe UI", 11), wraplength=630, justify="left").pack(
            anchor="w", padx=14, pady=(2, 6))
        # uyarı satırının yeri: liste kutusunun hemen üstü (CTkScrollableFrame'e 'before=' verilemiyor)
        self.warn_slot = ctk.CTkFrame(self, fg_color="transparent", height=0)
        self.warn_slot.pack(fill="x", padx=12)
        self.warn = ctk.CTkFrame(self.warn_slot, fg_color=PANEL2, border_width=1, border_color=AMBER)
        self.warn_label = ctk.CTkLabel(self.warn, text="Bazı eklentiler için gereken paketler kurulu değil.",
                                       text_color=AMBER, font=("Segoe UI", 11))
        self.warn_label.pack(side="left", padx=10, pady=8)
        self.install_btn = ctk.CTkButton(self.warn, text="Paketleri kur", width=120, command=self._install)
        self.install_btn.pack(side="right", padx=10, pady=8)
        self.list = ctk.CTkScrollableFrame(self, fg_color=PANEL)
        self.list.pack(fill="both", expand=True, padx=12, pady=(4, 6))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 12))
        self.status = ctk.CTkLabel(bar, text="", text_color=MUTED, font=("Segoe UI", 11), anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(bar, text="Kapat", width=80, fg_color=PANEL2, hover_color=CYAN, command=self.close).pack(
            side="right", padx=(6, 0))
        self.apply_btn = ctk.CTkButton(bar, text="Uygula", width=100, command=self._apply)
        self.apply_btn.pack(side="right")
        self.rows = {}
        self._build()
        self.after(1500, self._tick)

    def _build(self):
        try:
            self._build_inner()
        except Exception as ex:
            import traceback
            try:
                with open(os.path.join("data", "hatalar.log"), "a", encoding="utf-8") as f:
                    f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] Eklentiler penceresi\n{traceback.format_exc()}")
            except Exception:
                pass
            self.status.configure(text=f"Liste gösterilemedi: {ex}", text_color=AMBER)

    def _build_inner(self):
        for w in self.list.winfo_children():
            w.destroy()
        self.rows = {}
        liste = MCPX.liste(self.app.cfg)
        paket_eksik = not MCPX.available() or any("paketi kurulu değil" in x for e in liste
                                                  for x in MCPX.eksikler(e, self.app.cfg))
        if paket_eksik:
            self.warn.pack(fill="x", pady=(0, 4))
        else:
            self.warn.pack_forget()
        for e in liste:
            try:
                self._row(e)
            except Exception as ex:          # bir satır bozuk olsa da diğerleri görünsün
                ctk.CTkLabel(self.list, text=f"{e.get('ad')}: gösterilemedi ({ex})", text_color=AMBER).pack(anchor="w")
        self._add_form()
        self._refresh_status()

    def _row(self, e):
        import webbrowser
        fr = ctk.CTkFrame(self.list, fg_color=PANEL2, border_width=1, border_color=LINE)
        fr.pack(fill="x", padx=4, pady=4)
        top = ctk.CTkFrame(fr, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 0))
        sw = ctk.CTkSwitch(top, text=e.get("baslik") or e["ad"], font=("Segoe UI", 13), text_color=TEXT,
                           progress_color=self.app._accent())
        if e.get("aktif"):
            sw.select()
        sw.pack(side="left")
        st = ctk.CTkLabel(top, text="", text_color=MUTED, font=("Segoe UI", 11))
        st.pack(side="right")
        if e.get("aciklama"):
            ctk.CTkLabel(fr, text=e["aciklama"], text_color=MUTED, font=("Segoe UI", 11), wraplength=600,
                         justify="left").pack(anchor="w", padx=12)
        entry = None
        if e.get("anahtar") or e.get("indir_url"):
            kr = ctk.CTkFrame(fr, fg_color="transparent")
            kr.pack(fill="x", padx=10, pady=(4, 0))
            if e.get("anahtar"):
                var = str((self.app.cfg.get("api_keys") or {}).get(e["anahtar"]) or "").strip()
                has = bool(var) and not var.startswith("BURAYA")
                entry = ctk.CTkEntry(kr, show="•", width=300,
                                     placeholder_text="anahtar girilmiş (değiştirmek için yapıştır)" if has
                                     else "anahtarı buraya yapıştır")
                entry.pack(side="left")
                if e.get("anahtar_url"):
                    ctk.CTkButton(kr, text="Anahtar al", width=90, fg_color=PANEL, hover_color=CYAN,
                                  command=lambda u=e["anahtar_url"]: webbrowser.open(u)).pack(side="left", padx=6)
            if e.get("indir_url"):
                ctk.CTkButton(kr, text="İndir", width=70, fg_color=PANEL, hover_color=CYAN,
                              command=lambda u=e["indir_url"]: webbrowser.open(u)).pack(side="left")
        if e.get("ipucu"):
            ctk.CTkLabel(fr, text=e["ipucu"], text_color=MUTED, font=("Segoe UI", 10), wraplength=600,
                         justify="left").pack(anchor="w", padx=12)
        if e.get("kaynak") == "ozel":
            ctk.CTkButton(fr, text="Kaldır", width=70, fg_color=PANEL, hover_color="#7f1d1d",
                          command=lambda a=e["ad"]: self._remove(a)).pack(anchor="e", padx=10, pady=(4, 0))
        ctk.CTkFrame(fr, fg_color="transparent", height=6).pack()
        self.rows[e["ad"]] = {"e": e, "switch": sw, "status": st, "entry": entry}

    def _add_form(self):
        fr = ctk.CTkFrame(self.list, fg_color=PANEL2, border_width=1, border_color=LINE)
        fr.pack(fill="x", padx=4, pady=(10, 4))
        ctk.CTkLabel(fr, text="➕ Kendi eklentini ekle", text_color=TEXT, font=("Segoe UI", 13)).pack(
            anchor="w", padx=12, pady=(8, 0))
        ctk.CTkLabel(fr, text="Eklentinin sayfasında genelde 'npx -y paket-adi' gibi bir satır olur; paket adını yaz. "
                              "Anahtar istiyorsa sayfada yazan değişken adını da gir (ör. SPOTIFY_TOKEN). Kendi "
                              "eklediğin eklentilerin her işlemi onay ister. Sadece güvendiğin eklentileri ekle.",
                     text_color=MUTED, font=("Segoe UI", 10), wraplength=600, justify="left").pack(anchor="w", padx=12)
        row = ctk.CTkFrame(fr, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=6)
        self.f_ad = ctk.CTkEntry(row, width=120, placeholder_text="ad (ör. spotify)")
        self.f_ad.pack(side="left")
        self.f_paket = ctk.CTkEntry(row, width=230, placeholder_text="npm paketi (ör. @firma/mcp-server)")
        self.f_paket.pack(side="left", padx=6)
        self.f_env = ctk.CTkEntry(row, width=150, placeholder_text="anahtar değişkeni (isteğe bağlı)")
        self.f_env.pack(side="left")
        ctk.CTkButton(row, text="Ekle", width=60, command=self._add_custom).pack(side="left", padx=6)
        self.f_msg = ctk.CTkLabel(fr, text="", text_color=AMBER, font=("Segoe UI", 10))
        self.f_msg.pack(anchor="w", padx=12, pady=(0, 6))

    def _add_custom(self):
        ok, msg = MCPX.ozel_ekle(self.f_ad.get(), self.f_paket.get(), self.f_env.get())
        if not ok:
            self.f_msg.configure(text=msg)
            return
        self._build()
        self.status.configure(text="Eklendi. Anahtar istiyorsa yapıştır, sonra Uygula'ya bas.", text_color=MUTED)

    def _remove(self, ad):
        from tkinter import messagebox
        if not messagebox.askyesno("FENIX", f"'{ad}' eklentisi kaldırılsın mı?", parent=self):
            return
        MCPX.ozel_sil(ad)
        self._build()
        self.status.configure(text="Kaldırıldı. Uygula'ya bas.", text_color=MUTED)

    def _refresh_status(self):
        for ad, r in self.rows.items():
            e = r["e"]
            durum = MCPX.sunucu_durumu(ad)
            eksik = MCPX.eksikler(e, self.app.cfg)
            if not r["switch"].get():
                text, col = "kapalı", MUTED
            elif durum and durum.startswith("hazır"):
                text, col = "✓ " + durum, "#34d399"
            elif eksik:
                text, col = "⚠ " + "; ".join(eksik), AMBER
            elif durum:
                text, col = durum, AMBER if durum.startswith("hata") else MUTED
            else:
                text, col = "Uygula'ya bas", MUTED
            r["status"].configure(text=text[:90], text_color=col)
        self.status.configure(text=MCPX._STATE.get("mesaj") or "")

    def _tick(self):
        if not self._alive or not self.winfo_exists():
            return
        try:
            self._refresh_status()
        except Exception:
            pass
        self.after(2000, self._tick)

    def _apply(self):
        secim = {ad: bool(r["switch"].get()) for ad, r in self.rows.items()}
        MCPX.secim_kaydet(secim)
        keys = self.app.cfg.setdefault("api_keys", {})
        for ad, r in self.rows.items():
            ent, name = r["entry"], r["e"].get("anahtar")
            val = (ent.get() if ent is not None else "").strip()
            if name and val:
                try:
                    save_key("config.yaml", name, val)
                    keys[name] = val
                    ent.delete(0, "end")
                except Exception as ex:
                    self.status.configure(text=f"Anahtar kaydedilemedi: {ex}", text_color=AMBER)
                    return
        self.apply_btn.configure(state="disabled", text="Başlatılıyor…")
        self.status.configure(text="Eklentiler yeniden başlatılıyor… (ilk seferde 20-30 sn sürebilir)")

        def run():
            MCPX.yeniden_baslat(self.app.cfg, bildir=lambda t: self.app.after(0, lambda: self.app._flash_status(t, 5000)))
            self.app.after(0, self._done)
        threading.Thread(target=run, daemon=True).start()

    def _done(self):
        if self._alive and self.winfo_exists():
            self.apply_btn.configure(state="normal", text="Uygula")
            self._build()

    def _install(self):
        """Kurulum görünür bir pencerede yapılır ve FENIX kapanır: FENIX açıkken kendi kullandığı kütüphaneler
        Windows'ta kilitli olduğu için kurulum takılabiliyordu."""
        from tkinter import messagebox
        bat = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Eklentileri_Kur.bat")
        if not os.path.isfile(bat):
            self.warn_label.configure(text="Eklentileri_Kur.bat bulunamadı.")
            return
        if not messagebox.askyesno("FENIX", "Paketler ayrı bir pencerede kurulacak ve bunun için FENIX kapanacak.\n"
                                            "Kurulum bitince ('[OK]' yazısı) FENIX'i yeniden aç.\n\nDevam edilsin mi?",
                                   parent=self):
            return
        import subprocess
        try:
            flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
            subprocess.Popen(["cmd", "/c", bat] if os.name == "nt" else ["sh", bat], cwd=os.path.dirname(bat),
                             creationflags=flags)
        except Exception as ex:
            self.warn_label.configure(text=f"Kurulum başlatılamadı: {ex}")
            return
        self.app.after(300, self.app._finish_close)

    def close(self):
        self._alive = False
        self.destroy()


class HistoryWindow(ctk.CTkToplevel):
    """Geçmiş. İki görünüm:
    - Bu sohbet   : açık sohbetin günleri; o günkü mesajları (tam), notları, yaptıkları, raporları
    - Tüm sohbetler: gün gün bütün sohbetler, notlar, yapılanlar ve ekran kategorileri
    Not eklenebilir, gün (ya da sohbetin o günü) özetlenebilir."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._alive = True
        self.selected_day = datetime.date.today().isoformat()
        self.scope = "session" if app.session_id is not None else "all"
        self.title("FENIX • Geçmiş")
        self.geometry("900x640")
        self.configure(fg_color=BG)
        self.minsize(660, 440)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))
        self.scope_title = ctk.CTkLabel(top, text="", text_color=TEXT, font=(FONT_HEAD, 15, "bold"), anchor="w")
        self.scope_title.pack(side="left", fill="x", expand=True)
        self.scope_seg = ctk.CTkSegmentedButton(top, values=[i18n.tr("Bu sohbet"), i18n.tr("Tüm sohbetler")], selected_color=_THEME['base'],
                                                selected_hover_color="#34d399", unselected_color=PANEL2,
                                                command=self._on_scope)
        self.scope_seg.pack(side="right")

        self.days_frame = ctk.CTkScrollableFrame(self, width=150, fg_color=PANEL, corner_radius=0,
                                                 label_text="GÜNLER", label_text_color=MUTED)
        self.days_frame.grid(row=1, column=0, sticky="nsew")

        self.view = ctk.CTkTextbox(self, fg_color=PANEL2, text_color=TEXT, font=("Segoe UI", 12), wrap="word")
        self.view.grid(row=1, column=1, sticky="nsew", padx=10, pady=(6, 6))
        self.view.tag_config("h", foreground=_THEME['base'])
        self.view.tag_config("time", foreground=MUTED)
        self.view.tag_config("user", foreground=CYAN)
        self.view.tag_config("note", foreground=AMBER)
        self.view.tag_config("muted", foreground=MUTED)
        self.view.tag_config("sesslink", foreground=CYAN, underline=True)
        self.view._textbox.tag_bind("sesslink", "<Enter>", lambda e: self.view._textbox.configure(cursor="hand2"))
        self.view._textbox.tag_bind("sesslink", "<Leave>", lambda e: self.view._textbox.configure(cursor="xterm"))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        bar.grid_columnconfigure(0, weight=1)
        self.note_entry = ctk.CTkEntry(bar, placeholder_text="Not ekle...", fg_color=PANEL2,
                                       text_color=TEXT, height=38)
        self.note_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.note_entry.bind("<Return>", lambda e: self.add_note())
        ctk.CTkButton(bar, text="＋ Not ekle", width=100, height=38, fg_color=_THEME['base'], hover_color=_THEME['hover'],
                      command=self.add_note).grid(row=0, column=1, padx=(0, 6))
        self.sum_btn = ctk.CTkButton(bar, text="✨ Günü özetle", width=130, height=38, fg_color=PANEL,
                                     hover_color=CYAN, command=self.summarize)
        self.sum_btn.grid(row=0, column=2)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.set_scope(self.scope)

    # ---- kapsam ----
    def _sid(self):
        return self.app.session_id if self.scope == "session" else None

    def _on_scope(self, value):
        self.set_scope("session" if value == i18n.tr("Bu sohbet") else "all")

    def set_scope(self, scope):
        if scope == "session" and self.app.session_id is None:
            scope = "all"
        self.scope = scope
        self.scope_seg.set(i18n.tr("Bu sohbet") if scope == "session" else i18n.tr("Tüm sohbetler"))
        if scope == "session":
            sess = self.app.memory.get_session(self.app.session_id)
            self.scope_title.configure(text=f"📜 {sess['title'] if sess else 'Sohbet'}")
            self.sum_btn.configure(text="✨ Bu günü özetle")
            days = self.app.memory.get_days(session_id=self.app.session_id)
            if self.selected_day not in days:
                self.selected_day = days[0]
        else:
            self.scope_title.configure(text="📜 Tüm sohbetler")
            self.sum_btn.configure(text="✨ Günü özetle")
        self.show_day(self.selected_day)

    def on_session_changed(self):
        """Ana pencerede sohbet değişince çağrılır: 'Bu sohbet' görünümündeyse yeni sohbete geçer."""
        if self._alive:
            self.set_scope("session" if self.app.session_id is not None else "all")

    # ---- gün listesi ----
    def _day_label(self, day):
        today = datetime.date.today()
        if day == today.isoformat():
            return "Bugün"
        if day == (today - datetime.timedelta(days=1)).isoformat():
            return "Dün"
        try:
            d = datetime.date.fromisoformat(day)
            return d.strftime("%d.%m.%Y")
        except ValueError:
            return day

    def refresh_days(self):
        for w in self.days_frame.winfo_children():
            w.destroy()
        for day in self.app.memory.get_days(session_id=self._sid()):
            active = (day == self.selected_day)
            ctk.CTkButton(self.days_frame, text=self._day_label(day), anchor="w", height=30,
                          fg_color=_THEME['base'] if active else PANEL2,
                          hover_color=CYAN, text_color=BG if active else TEXT,
                          command=lambda d=day: self.show_day(d)).pack(fill="x", padx=4, pady=2)

    # ---- gün içeriği ----
    def show_day(self, day):
        self.selected_day = day
        sid = self._sid()
        data = self.app.memory.get_day_events(day, session_id=sid)
        activity = {} if sid is not None else self.app.memory.get_activity_summary(day)

        def hhmm(ts):
            return ts[11:16] if len(ts) >= 16 else ""

        self.view.configure(state="normal")
        self.view.delete("1.0", "end")
        self.view.insert("end", f"{self._day_label(day)}  ({day})\n", "h")

        empty = not (data["notes"] or data["events"] or data["conversations"] or activity)
        if empty:
            self.view.insert("end", "\nBu güne ait kayıt yok.\n", "muted")

        if data["notes"]:
            self.view.insert("end", "\n📝 NOTLAR\n", "h")
            for ts, source, content in data["notes"]:
                tag = {"user": "Not", "summary": "Özet", "auto": "Otomatik", "error": "Hata"}.get(source, source)
                self.view.insert("end", f" {hhmm(ts)}  ", "time")
                self.view.insert("end", f"[{tag}] ", "note")
                self.view.insert("end", f"{content}\n")

        if data["events"]:
            self.view.insert("end", "\n⚙️ YAPILANLAR\n", "h")
            for ts, kind, detail in data["events"]:
                self.view.insert("end", f" {hhmm(ts)}  ", "time")
                self.view.insert("end", f"{detail}\n" if kind == "action" else f"{kind}: {detail}\n")

        if activity:
            self.view.insert("end", "\n🖥 EKRAN KATEGORİLERİ\n", "h")
            for cat, mins in activity.items():
                self.view.insert("end", f" {cat}: {mins} dk\n")

        sessions = data.get("sessions") or []
        if sid is not None:
            msgs = data["conversations"]
            if msgs:
                self.view.insert("end", f"\n💬 MESAJLAR ({len(msgs)})\n", "h")
                for ts, role, content in msgs:
                    self.view.insert("end", f"\n {hhmm(ts)}  ", "time")
                    self.view.insert("end", "Sen: " if role == "user" else "FENIX: ", "user" if role == "user" else "h")
                    self.view.insert("end", f"{content}\n")
            sessions = []
        if sessions:
            self.view.insert("end", f"\n💬 SOHBETLER ({len(sessions)})\n", "h")
            self.view.insert("end", " Başlığa tıklayınca sohbet açılır.\n", "muted")
            for g in sessions:
                tag = f"sess_{g['id']}"
                n = len(g["messages"])
                self.view.insert("end", "\n ▸ ", "time")
                self.view.insert("end", g["title"], ("sesslink", tag))
                self.view.insert("end", f"   {hhmm(g['first'])}–{hhmm(g['last'])} • {n} mesaj\n", "time")
                if g["id"] is not None:
                    self.view.tag_bind(tag, "<Button-1>", lambda e, i=g["id"]: self._open_session(i))
                shown = g["messages"] if n <= 6 else g["messages"][:3] + [None] + g["messages"][-2:]
                for m in shown:
                    if m is None:
                        self.view.insert("end", f"     … {n - 5} mesaj daha …\n", "muted")
                        continue
                    ts, role, content = m
                    one = content.replace("\n", " ")
                    one = one if len(one) <= 160 else one[:157] + "…"
                    self.view.insert("end", f"     {hhmm(ts)}  ", "time")
                    self.view.insert("end", "Sen: " if role == "user" else "FENIX: ", "user" if role == "user" else "h")
                    self.view.insert("end", f"{one}\n")

        self.view.configure(state="disabled")
        self.view.yview_moveto(0)
        self.refresh_days()

    def refresh(self):
        """Dışarıdan (yeni kayıt geldiğinde) çağrılır; seçili günü yeniden çizer."""
        if self._alive:
            if self.scope == "session" and self.app.session_id is not None:
                sess = self.app.memory.get_session(self.app.session_id)
                if sess:
                    self.scope_title.configure(text=f"📜 {sess['title']}")
            self.show_day(self.selected_day)

    # ---- eylemler ----
    def add_note(self):
        text = self.note_entry.get().strip()
        if not text:
            return
        self.note_entry.delete(0, "end")
        self.app.memory.add_note(text, source="user")
        # Not, görüntülenen güne değil kayıt anına (bugüne) eklenir; bugünü göster
        self.show_day(datetime.date.today().isoformat())

    def summarize(self):
        sid = self._sid()
        self.app.run_day_summary(self.selected_day, session_id=sid)

    def close(self):
        self._alive = False
        self.destroy()


# =====================================================================
#  ANA UYGULAMA
# =====================================================================
# ---------------- Markdown -> biçimli metin (rapor görüntüleyici) ----------------
_INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[\d+(?:\s*[,\-–]\s*\d+)*\]|\[?kaynaklarda bulunamadı\]?)", re.IGNORECASE)


def _setup_md_tags(tb):
    """tk.Text üzerinde rapor etiketleri (CTkTextbox fontlu etikete izin vermediği için iç widget'a)."""
    tb.configure(font=("Segoe UI", 12), spacing1=2, spacing3=2, padx=14, pady=10)
    tb.tag_configure("h1", font=(FONT_HEAD, 19, "bold"), foreground=_THEME['base'], spacing1=6, spacing3=10)
    tb.tag_configure("h2", font=(FONT_HEAD, 15, "bold"), foreground=CYAN, spacing1=14, spacing3=6)
    tb.tag_configure("h3", font=(FONT_HEAD, 13, "bold"), foreground=TEXT, spacing1=10, spacing3=4)
    tb.tag_configure("b", font=(FONT_HEAD, 12, "bold"), foreground="#ffffff")
    tb.tag_configure("code", font=("Consolas", 11), foreground=AMBER)
    tb.tag_configure("cite", foreground=MUTED, font=("Segoe UI", 10))
    tb.tag_configure("missing", foreground="#f59e0b")
    tb.tag_configure("table", font=("Consolas", 11), foreground=TEXT, lmargin1=8, lmargin2=8)
    tb.tag_configure("thead", font=("Consolas", 11, "bold"), foreground=CYAN, lmargin1=8, lmargin2=8)
    tb.tag_configure("muted", foreground=MUTED, font=("Segoe UI", 10, "italic"))
    tb.tag_configure("bullet", lmargin1=12, lmargin2=30)
    tb.tag_configure("src", font=("Segoe UI", 11), foreground=MUTED, lmargin1=8, lmargin2=34)


def _md_inline(tb, text, base=()):
    for part in _INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            inner = part[2:-2]
            tag = "missing" if "bulunamad" in inner.lower() else "b"
            tb.insert("end", inner.strip("[]") if tag == "missing" else inner, base + (tag,))
        elif part.startswith("`") and part.endswith("`"):
            tb.insert("end", part[1:-1], base + ("code",))
        elif "bulunamad" in part.lower():
            tb.insert("end", part.strip("[]"), base + ("missing",))
        elif re.fullmatch(r"\[\d+(?:\s*[,\-–]\s*\d+)*\]", part):
            tb.insert("end", part, base + ("cite",))
        else:
            tb.insert("end", part, base)


def _md_table(tb, rows):
    import textwrap
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c or "--") for c in r)]
    if not cells:
        return
    ncol = max(len(r) for r in cells)
    cells = [r + [""] * (ncol - len(r)) for r in cells]
    cells = [[re.sub(r"\*\*|`", "", c) for c in r] for r in cells]
    maxw = max(12, min(40, 110 // ncol))
    widths = [min(maxw, max(len(r[i]) for r in cells)) for i in range(ncol)]
    sep = "┼".join("─" * (w + 2) for w in widths)
    for ri, row in enumerate(cells):
        wrapped = [textwrap.wrap(c, w) or [""] for c, w in zip(row, widths)]
        for li in range(max(len(x) for x in wrapped)):
            line = "│".join(f" {(x[li] if li < len(x) else ''):<{w}} " for x, w in zip(wrapped, widths))
            tb.insert("end", line + "\n", ("thead",) if ri == 0 else ("table",))
        if ri == 0 or ri == len(cells) - 1:
            tb.insert("end", sep + "\n", ("table",))
    tb.insert("end", "\n")


def _gizli_yorum(satir):
    """Satırın tamamı tek bir <!-- ... --> yorumu mu (imza satırı)? Regex yerine düz kontrol (CodeQL #4/#5)."""
    st = (satir or "").strip()
    return st.startswith("<!--") and st.endswith("-->") and "-->" not in st[4:-3]


def render_markdown(textbox, md):
    """CTkTextbox içine raporu biçimli yazar: başlıklar, kalın, tablo, maddeler, atıflar, kaynaklar."""
    tb = textbox._textbox
    _setup_md_tags(tb)
    textbox.configure(state="normal")
    tb.delete("1.0", "end")
    lines = md.splitlines()
    lines = [x for x in lines if not _gizli_yorum(x)]   # gizli yorumlar (imza) gösterilmez
    i, in_sources = 0, False
    while i < len(lines):
        line = lines[i]
        st = line.strip()
        if st.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            _md_table(tb, block)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", st)
        if m:
            level = min(len(m.group(1)), 3)
            title = m.group(2).replace("**", "")
            in_sources = bool(re.match(r"(kaynak|taranan|referans)", title.lower()))
            tb.insert("end", title + "\n", (f"h{level}",))
        elif re.fullmatch(r"-{3,}|\*{3,}|_{3,}", st):
            tb.insert("end", "\n")
        elif re.fullmatch(r"_.+_", st):
            tb.insert("end", st.strip("_") + "\n", ("muted",))
        elif in_sources and st:
            tb.insert("end", st + "\n", ("src",))
        elif re.match(r"^\s*[-*+]\s+", line):
            tb.insert("end", "• ", ("bullet",))
            _md_inline(tb, re.sub(r"^\s*[-*+]\s+", "", line), ("bullet",))
            tb.insert("end", "\n")
        elif re.match(r"^\s*\d+[.)]\s+", line):
            _md_inline(tb, line.strip(), ("bullet",))
            tb.insert("end", "\n")
        else:
            _md_inline(tb, line)
            tb.insert("end", "\n")
        i += 1
    textbox.configure(state="disabled")
    tb.yview_moveto(0)


class NobetDialog(ctk.CTkToplevel):
    """Kapatırken sorulan seçim: nöbette kal (pencere kapanır, hafif izleme sürer) / tamamen kapat / vazgeç."""

    def __init__(self, app):
        super().__init__(app)
        self.result = None
        self.remember = False
        self.title("FENIX'i kapat")
        self.geometry("460x330")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.transient(app)
        ctk.CTkLabel(self, text="🌙 Nöbette kalayım mı?", text_color=TEXT, font=(FONT_HEAD, 16, "bold"),
                     anchor="w").pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(self, text=("Pencereyi kapatırım ama küçük bir izleme işlemi (yaklaşık 40-60 MB) sağ alttaki simgede "
                                 "çalışmaya devam eder: indirdiğin dosyalara, kopyaladığın linklere ve açılışta başlayan "
                                 "programlara bakar, bir sorun görürse bildirir. Ekranı ve mikrofonu izlemez, hiçbir şeyi "
                                 "kaydetmez. Simgeden istediğin an kapatabilirsin."),
                     text_color=MUTED, font=("Segoe UI", 11), wraplength=420, justify="left", anchor="w").pack(
            fill="x", padx=18)
        self.var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Seçimimi hatırla (bir daha sorma)", variable=self.var, text_color=TEXT,
                        fg_color=_THEME['base'], font=("Segoe UI", 11)).pack(anchor="w", padx=18, pady=(12, 8))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(4, 0))
        ctk.CTkButton(row, text="🌙 Nöbette kal", fg_color=_THEME['base'], hover_color=_THEME['hover'], width=130,
                      command=lambda: self._pick("nobet")).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row, text="Tamamen kapat", fg_color="#7f1d1d", hover_color="#b91c1c", width=120,
                      command=lambda: self._pick("kapat")).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row, text="Vazgeç", fg_color=PANEL2, hover_color=CYAN, width=80,
                      command=self._cancel).pack(side="left")
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def _pick(self, what):
        self.result = what
        self.remember = bool(self.var.get())
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class LearnedWindow(ctk.CTkToplevel):
    """🎓 Öğrendiklerim: komut hafızasındaki kalıplar (senin öğrettiklerin, üretilen söylenişler, eğitim turu).
    Tek tek silebilir, eğitim turunu ve bilgisayar taramasını başlatabilirsin."""
    MAX_ROWS = 120

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("FENIX • Öğrendiklerim")
        self.geometry("780x620")
        self.configure(fg_color=BG)
        self.minsize(560, 420)
        ctk.CTkLabel(self, text="🎓 Öğrendiğim komutlar", text_color=TEXT, font=(FONT_HEAD, 15, "bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(12, 0))
        self.info = ctk.CTkLabel(self, text="", text_color=MUTED, font=("Segoe UI", 10), anchor="w",
                                 wraplength=720, justify="left")
        self.info.pack(fill="x", padx=14, pady=(0, 6))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12)
        bar.grid_columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(bar, placeholder_text="🔍 Komutlarda ara...", fg_color=PANEL2, text_color=TEXT)
        self.search.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.search.bind("<KeyRelease>", lambda e: self.after(200, self.refresh))
        self.kind = ctk.CTkSegmentedButton(bar, values=i18n.tr_values(["Hepsi", "Öğrettiklerim", "Üretilen", "Eğitim"]),
                                           command=lambda v: self.refresh(), unselected_color=PANEL2)
        self.kind.set(i18n.tr("Hepsi"))
        self.kind.grid(row=0, column=1)
        self.list = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=8)
        self.list.pack(fill="both", expand=True, padx=12, pady=8)
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkButton(foot, text="Eğitim turunu çalıştır", fg_color=_THEME['base'], hover_color=_THEME['hover'], width=170,
                      command=self.train).pack(side="left", padx=(0, 6))
        ctk.CTkButton(foot, text="Bilgisayarı tara", fg_color=PANEL2, hover_color=CYAN, width=130,
                      command=self.scan).pack(side="left", padx=(0, 6))
        ctk.CTkButton(foot, text="Yenile", fg_color=PANEL2, hover_color=CYAN, width=70,
                      command=self.refresh).pack(side="left")
        ctk.CTkButton(foot, text="Hepsini sil", fg_color="#7f1d1d", hover_color="#b91c1c", width=100,
                      command=self.clear).pack(side="right")
        self.msg = ctk.CTkLabel(self, text="", text_color=AMBER, font=("Segoe UI", 10))
        self.msg.pack(pady=(0, 6))
        self.refresh()

    def _filtered(self):
        q = cmem.fold(self.search.get())
        want = {i18n.tr("Öğrettiklerim"): "kullanim", i18n.tr("Üretilen"): "uretilen", i18n.tr("Eğitim"): "egitim"}.get(self.kind.get())
        rows = [e for e in cmem.entries() if (not want or e.get("kaynak") == want)
                and (not q or q in cmem.fold(e.get("gorunen", "")) or q in e.get("arac", ""))]
        rows.sort(key=lambda e: (e.get("kaynak") != "kullanim", -e.get("sayac", 0), e.get("arac", ""),
                                 e.get("gorunen", "")))
        return rows

    def refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        st = cmem.stats(fx.FUNCTION_SCHEMAS)
        inv = pc_tools._inventory()
        _t = i18n.tr
        self.info.configure(text=(
            _t(f"{st['kayit']} kalıp ({st['kullanimdan']} senin öğrettiğin, {st['uretilen']} üretilen söyleniş, "
               f"{st['egitimden']} eğitim turundan). Yapay zekâya gitmeden {st['yerel']} kez çalıştırdım.") + " "
            + (_t(f"Bilgisayar envanteri: {len(inv.get('uygulamalar', []))} uygulama ({inv.get('tarih', '')[:10]}).") + " "
               if inv else _t("Bilgisayar henüz taranmadı.") + " ")
            + (_t(f"Eğitimi bekleyen araçlar: {', '.join(st['egitim_bekleyen'])}.") if st.get("egitim_bekleyen") else "")))
        rows = self._filtered()
        if not rows:
            ctk.CTkLabel(self.list, text="Henüz öğrenilmiş komut yok. Normal/Devil modda 'ses aç' gibi komutlar "
                                         "verdikçe ya da eğitim turundan sonra burada görünür.",
                         text_color=MUTED, wraplength=600).pack(pady=12)
        for e in rows[:self.MAX_ROWS]:
            row = ctk.CTkFrame(self.list, fg_color=PANEL2, corner_radius=6)
            row.pack(fill="x", padx=4, pady=2)
            tag = {"kullanim": "👤", "uretilen": "✨", "egitim": "🎓"}.get(e.get("kaynak"), "")
            ctk.CTkLabel(row, text=f"{tag} {e.get('gorunen', '')}", text_color=TEXT, anchor="w", width=250,
                         font=(FONT_HEAD, 12, "bold")).pack(side="left", padx=8, pady=5)
            args = json.dumps(e.get("args", {}), ensure_ascii=False)
            ctk.CTkLabel(row, text=f"→ {e.get('arac')} {args[:60]}", text_color=CYAN, anchor="w",
                         font=("Consolas", 10)).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(row, text=f"{e.get('sayac', 0)}×", text_color=MUTED, width=36).pack(side="left")
            ctk.CTkButton(row, text="✕", width=28, fg_color="#7f1d1d", hover_color="#b91c1c",
                          command=lambda i=e["id"]: self.delete(i)).pack(side="right", padx=6)
        if len(rows) > self.MAX_ROWS:
            ctk.CTkLabel(self.list, text=f"... ve {len(rows) - self.MAX_ROWS} kalıp daha (aramayı daralt).",
                         text_color=MUTED).pack(pady=6)

    def delete(self, entry_id):
        cmem.remove(entry_id)
        self.refresh()

    def clear(self):
        if cmem.stats()["kayit"] and fx._confirm("Öğrenilen komutlar silinecek",
                                                 "Hafızadaki bütün komut kalıpları silinsin mi?",
                                                 "Eğitim turu bir sonraki açılışta yeniden yapılır."):
            n = cmem.clear_all()
            self.msg.configure(text=f"{n} kalıp silindi.")
            self.refresh()

    def train(self):
        mc = self.app.cfg["modes"]["normal"]
        self.msg.configure(text="Eğitim turu başladı; ilerleme sohbette ve soldaki panelde görünür.")
        self.app._pipe["task"] = "Komut eğitim turu"
        self.app._run_task(lambda: self.app.agent.train_commands(mc))

    def scan(self):
        self.msg.configure(text="Bilgisayar taranıyor...")
        self.app._pipe["task"] = "Bilgisayar taraması"
        self.app._run_task(lambda: fx.WHITELISTED_FUNCTIONS["scan_pc"]().get("message", "Taradım."))

    def close(self):
        self.destroy()


class RemindersWindow(ctk.CTkToplevel):
    """⏰ Hatırlatmalar: bekleyenleri listeler, iptal eder, elle yenisini ekler."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("FENIX • Hatırlatmalar")
        self.geometry("560x520")
        self.configure(fg_color=BG)
        self.minsize(420, 360)
        ctk.CTkLabel(self, text="⏰ Bekleyen hatırlatmalar", text_color=TEXT, font=(FONT_HEAD, 15, "bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(self, text="Sohbetten de kurabilirsin: \"yarın 15:00'te toplantıyı hatırlat\", "
                                "\"20 dakika sonra çayı hatırlat\"", text_color=MUTED, font=("Segoe UI", 10),
                     anchor="w").pack(fill="x", padx=14)
        self.list = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=8)
        self.list.pack(fill="both", expand=True, padx=12, pady=8)
        add = ctk.CTkFrame(self, fg_color="transparent")
        add.pack(fill="x", padx=12, pady=(0, 12))
        add.grid_columnconfigure(0, weight=1)
        self.what = ctk.CTkEntry(add, placeholder_text="Ne hatırlatılsın?", fg_color=PANEL2, text_color=TEXT)
        self.what.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.when = ctk.CTkEntry(add, placeholder_text="Ne zaman? (ör. 18:30, yarın 9:00)", width=190,
                                 fg_color=PANEL2, text_color=TEXT)
        self.when.grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(add, text="＋ Ekle", width=80, fg_color=_THEME['base'], hover_color=_THEME['hover'], command=self.add).grid(
            row=0, column=2)
        self.msg = ctk.CTkLabel(self, text="", text_color=AMBER, font=("Segoe UI", 10))
        self.msg.pack(pady=(0, 6))
        self.refresh()

    def refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        pend = self.app.reminders.pending()
        if not pend:
            ctk.CTkLabel(self.list, text="Bekleyen hatırlatma yok.", text_color=MUTED).pack(pady=12)
        for r in pend:
            row = ctk.CTkFrame(self.list, fg_color=PANEL2, corner_radius=6)
            row.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(row, text=human_when(r["due"]), text_color=CYAN, width=120, anchor="w").pack(
                side="left", padx=8, pady=6)
            ctk.CTkLabel(row, text=r["text"], text_color=TEXT, anchor="w", wraplength=280, justify="left").pack(
                side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="✕", width=30, fg_color="#7f1d1d", hover_color="#b91c1c",
                          command=lambda i=r["id"]: self.cancel(i)).pack(side="right", padx=6)

    def cancel(self, rid):
        self.app.reminders.cancel(rid)
        self.refresh()

    def add(self):
        text, when = self.what.get().strip(), self.when.get().strip()
        due = parse_when(when) if when else None
        if not text or not due or due <= datetime.datetime.now():
            self.msg.configure(text="Metni ve geçerli, ileri bir zamanı yaz (ör. 18:30, yarın 9:00, 20 dakika sonra).")
            return
        self.app.reminders.add(due, text, self.app.session_id)
        self.what.delete(0, "end")
        self.when.delete(0, "end")
        self.msg.configure(text=f"Kuruldu: {human_when(due)} — {text}")
        self.refresh()

    def close(self):
        self.destroy()


class ReportsWindow(ctk.CTkToplevel):
    """Raporlarım: arama, rapor listesi, biçimli görüntüleme, sabitle / sil / klasörde göster."""

    def __init__(self, app, select_path=None):
        super().__init__(app)
        self.app = app
        self.store = app.reports
        self.selected = None
        self.title("FENIX • Raporlarım")
        self.geometry("1180x760")
        self.configure(fg_color=BG)
        self.minsize(820, 480)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        self.search = ctk.CTkEntry(top, placeholder_text="🔍 Raporlarda ara...", fg_color=PANEL2,
                                   text_color=TEXT, height=34, width=270)
        self.search.pack(fill="x")
        self.search.bind("<KeyRelease>", lambda e: self.after(250, self.refresh_list))

        self.list_frame = ctk.CTkScrollableFrame(self, width=290, fg_color=PANEL, corner_radius=0)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 6))

        self.head = ctk.CTkLabel(self, text="", text_color=MUTED, font=("Segoe UI", 11), anchor="w")
        self.head.grid(row=0, column=1, sticky="ew", padx=12, pady=(10, 4))
        self.view = ctk.CTkTextbox(self, fg_color=PANEL2, text_color=TEXT, wrap="word")
        self.view.grid(row=1, column=1, sticky="nsew", padx=10, pady=(0, 6))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.info = ctk.CTkLabel(bar, text="", text_color=MUTED, font=("Segoe UI", 10))
        self.info.pack(side="left")
        ctk.CTkButton(bar, text="Kapat", width=80, fg_color=PANEL, hover_color=CYAN,
                      command=self.close).pack(side="right")
        self.del_btn = ctk.CTkButton(bar, text="🗑 Sil", width=80, fg_color="#7f1d1d", hover_color="#b91c1c",
                                     command=self.delete_selected)
        self.del_btn.pack(side="right", padx=(0, 6))
        self.folder_btn = ctk.CTkButton(bar, text="📂 Klasörde göster", width=140, fg_color=PANEL,
                                        hover_color=CYAN, command=self.show_in_folder)
        self.folder_btn.pack(side="right", padx=(0, 6))
        self.pin_btn = ctk.CTkButton(bar, text="📌 Sabitle", width=110, fg_color=PANEL, hover_color=CYAN,
                                     command=self.toggle_pin)
        self.pin_btn.pack(side="right", padx=(0, 6))
        ctk.CTkButton(bar, text="⬇ PDF", width=80, fg_color=PANEL, hover_color=CYAN,
                      command=lambda: self.export_report("pdf")).pack(side="right", padx=(0, 6))
        ctk.CTkButton(bar, text="⬇ Word", width=90, fg_color=PANEL, hover_color=CYAN,
                      command=lambda: self.export_report("docx")).pack(side="right", padx=(0, 6))

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_list()
        items = self.store.list()
        if select_path:
            self.select(select_path)
        elif items:
            self.select(items[0]["path"])
        else:
            render_markdown(self.view, i18n.tr("# Henüz rapor yok\n\nDevil modda bir araştırma iste "
                                       "(ör. *en iyi orta segment ekran kartlarını araştır*); rapor burada görünür."))

    def _norm(self, p):
        return os.path.normcase(os.path.abspath(p))

    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        q = self.search.get().strip()
        items = self.store.list(q)
        for it in items:
            active = self.selected and self._norm(it["path"]) == self._norm(self.selected)
            icon = ("📌 " if it["pinned"] else "") + ("🗜 " if it["compressed"] else "")
            text = f"{icon}{it['title'][:46]}\n{it['date']:%d.%m.%Y %H:%M}  •  {human_size(it['size'])}"
            ctk.CTkButton(self.list_frame, text=text, anchor="w", height=48, font=("Segoe UI", 11),
                          fg_color=_THEME['base'] if active else PANEL2, hover_color=_THEME['hover'],
                          text_color=BG if active else TEXT,
                          command=lambda p=it["path"]: self.select(p)).pack(fill="x", padx=4, pady=2)
        allitems = self.store.list() if q else items
        total = sum(i["size"] for i in allitems)
        c = self.store.cfg
        self.info.configure(text=(f"{len(allitems)} rapor • {human_size(total)} / {c['max_total_mb']} MB  •  "
                                  f"en fazla {c['max_count']} rapor; {c['compress_after_days']} günden eskiler "
                                  f"sıkıştırılır, 📌 sabitlenenler silinmez"))

    def select(self, path):
        # sıkıştırılmış/açılmış adı değişmiş olabilir: aynı rapora karşılık gelen dosyayı bul
        cand = [i for i in self.store.list() if self.store._key(i["path"]) == self.store._key(path)]
        if not cand:
            return
        it = cand[0]
        self.selected = it["path"]
        try:
            render_markdown(self.view, self.store.read(it["path"]))
        except Exception as e:
            render_markdown(self.view, i18n.tr(f"# Rapor açılamadı\n\n{e}"))
        self.head.configure(text=f"{it['date']:%d.%m.%Y %H:%M}  •  {human_size(it['size'])}  •  "
                                 f"{os.path.basename(it['path'])}")
        self.pin_btn.configure(text="📌 Sabitlemeyi kaldır" if it["pinned"] else "📌 Sabitle")
        self.refresh_list()

    def toggle_pin(self):
        if not self.selected:
            return
        self.store.toggle_pin(self.selected)
        self.select(self.selected)

    def delete_selected(self):
        if not self.selected:
            return
        from tkinter import messagebox
        if not messagebox.askyesno("Raporu sil", "Bu rapor kalıcı olarak silinsin mi?", parent=self):
            return
        try:
            self.store.delete(self.selected)
        except Exception as e:
            messagebox.showerror("Silinemedi", str(e), parent=self)
            return
        self.selected = None
        items = self.store.list()
        if items:
            self.select(items[0]["path"])
        else:
            self.refresh_list()
            render_markdown(self.view, i18n.tr("# Rapor kalmadı"))
            self.head.configure(text="")

    def show_in_folder(self):
        target = os.path.abspath(self.selected or self.store.folder)
        try:
            if os.name == "nt":
                import subprocess
                subprocess.Popen(["explorer", "/select,", target] if self.selected else ["explorer", target])
        except Exception as e:
            print(f"[RAPOR] klasör açılamadı: {e}")

    def export_report(self, fmt):
        """Seçili raporu Word (.docx) ya da PDF olarak data/raporlar/disa_aktarilan/ altına kaydeder."""
        if not self.selected:
            return
        from tkinter import messagebox
        try:
            out_path = self.store.export(self.selected, fmt)
        except Exception as e:
            messagebox.showerror("Dışa aktarılamadı", str(e), parent=self)
            return
        if messagebox.askyesno("Dışa aktarıldı", f"Kaydedildi:\n{out_path}\n\nKlasörde göster?", parent=self):
            try:
                if os.name == "nt":
                    import subprocess
                    subprocess.Popen(["explorer", "/select,", os.path.abspath(out_path)])
            except Exception as e:
                print(f"[RAPOR] klasör açılamadı: {e}")

    def close(self):
        self.destroy()


class SplashScreen(ctk.CTkToplevel):
    """Açılış ekranı: ana pencere hazırlanırken holografik bir yükleme ekranı gösterir.
    Ana pencere hazır olunca kapanır. (Açılış birkaç saniye sürünce 'açılmadı' sanılıyordu.)"""
    W, H = 520, 320

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=BG)
        try:
            self.attributes("-topmost", True)
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            # Windows ekran ölçeği (%125, %150...) pencere boyutunu büyütür ama tuvali büyütmez: boyut ölçeğe bölünür
            try:
                sc = ctk.ScalingTracker.get_window_scaling(self) or 1.0
            except Exception:
                sc = 1.0
            self.geometry(f"{round(self.W / sc)}x{round(self.H / sc)}+{(sw - self.W) // 2}+{(sh - self.H) // 2}")
        except Exception:
            self.geometry(f"{self.W}x{self.H}")
        self.cv = ctk.CTkCanvas(self, bg=BG, highlightthickness=1, highlightbackground=LINE,
                                width=self.W, height=self.H)
        self.cv.pack(fill="both", expand=True)
        cv, acc = self.cv, MODE_ACCENT["normal"]["base"]
        for x in range(0, self.W, 32):
            cv.create_line(x, 0, x, self.H, fill=GRID)
        for y in range(0, self.H, 32):
            cv.create_line(0, y, self.W, y, fill=GRID)
        self.cx, self.cy = self.W // 2, 128
        self.bars = [cv.create_line(0, 0, 0, 0, fill=acc, width=2, capstyle="round") for _ in range(48)]
        cv.create_oval(self.cx - 40, self.cy - 40, self.cx + 40, self.cy + 40, outline=acc, width=2, fill=BG)
        self.core = cv.create_oval(0, 0, 0, 0, fill=acc, width=0)
        cv.create_text(self.cx, 232, text="F · E · N · I · X", fill=TEXT, font=(FONT_HEAD, 22, "bold"))
        cv.create_text(self.cx, 260, text="MK-Agentic-System  ·  v" + FENIX_VERSION, fill=MUTED, font=(FONT_MONO, 9))
        self.msg = cv.create_text(24, self.H - 30, anchor="w", text="", fill=MUTED, font=(FONT_MONO, 9))
        cv.create_rectangle(24, self.H - 14, self.W - 24, self.H - 12, outline="", fill=PANEL2)
        self.bar = cv.create_rectangle(24, self.H - 14, 24, self.H - 12, outline="", fill=acc)
        self.phase = 0.0
        self.step("Başlatılıyor", 0.05)

    def _frame(self):
        self.phase += 0.35
        n = len(self.bars)
        for i, it in enumerate(self.bars):
            a = 2 * math.pi * i / n + self.phase * 0.1
            ln = 6 + 18 * abs(math.sin(i * 0.5 + self.phase))
            r0 = 50
            self.cv.coords(it, self.cx + r0 * math.cos(a), self.cy + r0 * math.sin(a),
                           self.cx + (r0 + ln) * math.cos(a), self.cy + (r0 + ln) * math.sin(a))
        rc = 24 + 4 * math.sin(self.phase)
        self.cv.coords(self.core, self.cx - rc, self.cy - rc, self.cx + rc, self.cy + rc)

    def step(self, text, frac):
        """Yükleme adımı: yazı + ilerleme çubuğu + bir animasyon karesi (ana pencere kurulurken çağrılır)."""
        try:
            self.cv.itemconfigure(self.msg, text=i18n.tr(text) + " ...")
            self.cv.coords(self.bar, 24, self.H - 14, 24 + (self.W - 48) * max(0.0, min(1.0, frac)), self.H - 12)
            self._frame()
            self.update()
        except Exception:
            pass


class FenixApp(ctk.CTk, *_DND_BASES):
    def __init__(self, cfg):
        super().__init__()
        self.withdraw()                 # ana pencere hazır olana kadar gizli; bu sırada açılış ekranı görünür
        try:
            self._splash = SplashScreen(self)
        except Exception as e:
            print(f"[AÇILIŞ EKRANI] {e}")
            self._splash = None
        if OGR:
            OGR.ensure_mode(cfg)       # config.yaml'da 'ogrenme' modu yoksa varsayılanı eklenir
        self.cfg = cfg
        self.title("F.E.N.I.X.")
        self.geometry("1200x720")
        # Tk nesneleri (font, resim) yalnızca ana iş parçacığında yok edilmeli. Otomatik çöp toplama
        # bir arka plan iş parçacığında (araştırma, dosya okuma) tetiklenirse Tk'ye oradan dokunur ve
        # uygulama donabilir. Bu yüzden otomatik toplama kapatılır, _tick içinde ana iş parçacığında yapılır.
        gc.disable()
        self._gc_counter = 0
        # Pencere ve görev çubuğu simgesi (Windows'ta .ico gerekir)
        try:
            if os.name == "nt" and os.path.exists("fenix.ico"):
                self.iconbitmap("fenix.ico")
        except Exception as e:
            print(f"[SİMGE] {e}")
        self.configure(fg_color=BG)
        self.minsize(1000, 620)

        # Durum
        self.mode_key = cfg.get("default_mode", "normal")
        if self.mode_key not in (cfg.get("modes") or {}):
            self.mode_key = "normal"
        _tts = user_settings.get("tts_enabled")      # son seçilen hal hatırlanır (yoksa config'teki varsayılan)
        self.tts_enabled = bool(cfg["audio"].get("tts_enabled", True) if _tts is None else _tts)
        self.ui_queue = queue.Queue()
        self._orb_phase = 0.0
        self._orb_state = "idle"   # idle | listening | thinking
        self._confirm_event = threading.Event()
        self._confirm_result = {"value": False}
        self._mic_recording = False
        self._windows = {}         # açık yan pencereler
        self._task_lock = threading.Lock()

        # Pipeline durumu
        self._pipe = {"steps": [], "labels": [], "idx": -1, "active": False,
                      "gen": 0, "start": 0.0, "stage_start": 0.0, "shown": 0.0}

        # Çekirdek
        self._splash_step("Hafıza açılıyor", 0.2)
        self.memory = Memory(cfg["memory"]["db_path"], cfg["memory"]["chroma_path"], cfg["api_keys"]["gemini"],
                             cross_chat=cfg["memory"].get("cross_chat", True), defer_semantic=True)
        _bk = cfg["api_keys"].get("gemini_yedek") or []
        try:
            from modules import nvidia
            nvidia.configure(cfg)       # NVIDIA: sohbet yedeği (Groq'tan sonra) + görme son yedeği
        except Exception:
            pass
        self._splash_step("Yapay zekâ bağlantıları hazırlanıyor", 0.35)
        self.llm = LLMClient(cfg["api_keys"]["gemini"], cfg["api_keys"].get("groq", ""),
                             fallbacks=cfg.get("gemini_fallbacks"),
                             gemini_backup_keys=[_bk] if isinstance(_bk, str) else list(_bk),
                             groq_fallbacks=cfg.get("groq_fallbacks"))
        self._cancel_event = threading.Event()
        self.llm.iptal = self._cancel_event.is_set      # 'Görevi durdur' model beklemesini de anında keser
        self.session_id = None          # açık sohbet (ilk mesajda oluşturulur)
        self.agent = Agent(self.llm, self.memory,
                           on_stage=lambda name: self.ui_queue.put(("stage", name)),
                           on_plan=lambda steps: self.ui_queue.put(("plan", list(steps))),
                           notify=lambda text: self.ui_queue.put(("pipeline_note", text)),
                           cancelled=self._cancel_event.is_set,
                           research_cfg=dict(cfg.get("deep_research") or {}, documents=cfg.get("documents") or {}),
                           command_cfg=cfg.get("komut_hafizasi") or {})
        self._attachments = []          # gönderilmeyi bekleyen ekli dosyalar
        self.after(400, self.memory.start_semantic)    # anlamsal hafıza pencere açıldıktan sonra arka planda yüklenir
        self.after(3000, YOLH.arka_planda_tara)        # proje klasörleri (içinde .git olanlar) günde bir taranır
        # eklentiler (MCP) pencere açıldıktan sonra arka planda başlar; hazır olunca durum satırında kısa not
        self.after(1500, lambda: MCPX.baslat(cfg, bildir=lambda t: self.after(0, lambda: self._flash_status(t, 5000))))
        if OGR:
            OGR.setup(self)             # öğrenme döngüsü (Öğrenme modu açıkken çalışır)
        self.after(150, self._apply_mode_theme)     # açılıştaki modun rengi her yere uygulansın
        self.reports = ReportStore("data/raporlar", cfg.get("reports"))
        threading.Thread(target=self._cleanup_reports, daemon=True).start()
        threading.Thread(target=self._cleanup_pasted, daemon=True).start()
        self._splash_step("Ses sistemi hazırlanıyor", 0.5)
        self.recorder = PushToTalkRecorder(cfg["audio"]["ptt_key"], cfg["audio"]["sample_rate"],
                                           device=cfg["audio"].get("input_device"))
        self.spotlight = Spotlight()
        self.stats = StatsTracker(self.memory)
        self.stats.start()

        # functions.py'yi arayüze bağla: onay kutusu + yapılan işlemleri Geçmiş'e not düş
        FBILGI.install(cfg)                 # kendini tanı aracı (modlar/modeller config'ten okunur)
        fx.set_confirm_handler(self._request_confirmation)
        fx.set_notify_handler(self._on_action_notify)
        fx.set_error_handler(self._record_error)
        fx.set_capture_handler(self._capture_screen_hidden)
        fx.set_memory(self.memory)
        self.reminders = ReminderStore(self.memory.conn)
        fx.set_reminder_store(self.reminders)
        fx.set_report_store(self.reports)
        _voice = user_settings.get("voice")
        if isinstance(_voice, dict):
            audio_io.set_prosody(**{k: v for k, v in _voice.items() if k in ("rate", "pitch", "volume")})
        self._reminders_shown = set()
        self._app_started = datetime.datetime.now()
        self._nobet_cfg = nobet.load_settings(cfg.get("nobet"))
        self._gozcu = None
        try:
            if nobet.is_running():           # pencere açıldı: nöbet işlemini devral (çift uyarı olmasın)
                nobet.stop_running()
        except Exception as e:
            print(f"[NÖBET] devralınamadı: {e}")
        threading.Thread(target=self._reminder_loop, daemon=True).start()
        threading.Thread(target=self._security_watch_loop, daemon=True).start()
        threading.Thread(target=self._command_training_loop, daemon=True).start()
        fx.set_search_keys(cfg.get("api_keys", {}))

        self._splash_step("Arayüz çiziliyor", 0.7)
        self._build_ui()
        self._splash_step("Son hazırlıklar", 0.92)
        self._setup_drag_drop()
        self._start_background()
        self._start_gozcu()
        self.after(40, self._tick)           # ~25 FPS orb + UI kuyruğu
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._splash_step("Hazır", 1.0)
        self.after(250, self._show_main)

    def _splash_step(self, text, frac):
        if getattr(self, "_splash", None):
            self._splash.step(text, frac)

    def _show_main(self):
        """Açılış ekranını kapatıp ana pencereyi gösterir."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass
        sp, self._splash = getattr(self, "_splash", None), None
        if sp:
            try:
                sp.destroy()
            except Exception:
                pass

    # ---------------- UI KURULUMU ----------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)   # sol menü
        self.grid_columnconfigure(1, weight=0)   # pipeline
        self.grid_columnconfigure(2, weight=1)   # merkez
        self.grid_columnconfigure(3, weight=1)   # sağ chat
        self.grid_rowconfigure(0, weight=1)

        self._build_left()
        self._build_pipeline()
        self._build_center()
        self._build_right()

    def _build_left(self):
        p = ctk.CTkFrame(self, width=230, fg_color=PANEL, corner_radius=0)
        p.grid(row=0, column=0, sticky="nsew")
        p.grid_propagate(False)
        p.pack_propagate(False)

        head = ctk.CTkFrame(p, fg_color="transparent")
        head.pack(fill="x", pady=(14, 6))
        self.brand_label = ctk.CTkLabel(head, text="F.E.N.I.X.", text_color=self._accent(),
                                        font=(FONT_HEAD, 19, "bold"))
        self.brand_label.pack()
        ctk.CTkLabel(head, text=imza.build_label(FENIX_VERSION), text_color=MUTED, font=("Segoe UI", 10)).pack()

        nb = ctk.CTkFrame(p, fg_color="transparent")
        nb.pack(fill="x", padx=12, pady=(4, 6))
        self.new_chat_btn = ctk.CTkButton(nb, text="＋  Yeni sohbet", height=36, fg_color=self._accent(),
                                          hover_color=self._accent_hover(), text_color=BG,
                                          font=(FONT_HEAD, 13, "bold"), command=self._new_chat)
        self.new_chat_btn.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(nb, text="🕶", width=40, height=36, fg_color=PANEL2, hover_color=CYAN, text_color=TEXT,
                      font=("Segoe UI", 15), command=lambda: self._new_chat(incognito=True)).pack(side="left",
                                                                                                    padx=(6, 0))
        self.session_search = ctk.CTkEntry(p, placeholder_text="🔍 Sohbetlerde ara", height=28, fg_color=PANEL2,
                                           text_color=TEXT, font=("Segoe UI", 11))
        self.session_search.pack(fill="x", padx=12, pady=(0, 4))
        self.session_search.bind("<KeyRelease>", lambda e: self.after(250, self._refresh_sessions))

        # Alt kısım (önce paketlenir ki liste kalan alanı doldursun)
        bottom = ctk.CTkFrame(p, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=(4, 8))
        self.load_label = ctk.CTkLabel(bottom, text="", text_color=MUTED, font=("Consolas", 10))
        self.load_label.pack(side="bottom", pady=(4, 0))
        self.tts_switch = ctk.CTkSwitch(bottom, text="Sesli cevap", command=self._toggle_tts,
                                        progress_color=self._accent(), font=("Segoe UI", 11))
        if self.tts_enabled:
            self.tts_switch.select()
        self.tts_switch.pack(side="bottom", pady=(6, 0))
        menu = ctk.CTkFrame(bottom, fg_color="transparent")
        menu.pack(side="bottom", fill="x", padx=10)
        menu.grid_columnconfigure((0, 1), weight=1)
        items = [("📜 Geçmiş", self._show_history), ("📄 Raporlar", self._show_reports),
                 ("⏰ Hatırlatma", self._show_reminders), ("🧠 Yetenekler", self._show_skills),
                 ("🧩 Eklentiler", self._show_plugins),
                 ("🎓 Öğrendiklerim", self._show_learned), ("📊 İstatistik", self._show_stats),
                 *([("🧪 Oyun alanı", self._show_lab)] if OGR else []),
                 ("🌙 Nöbete geç", self._go_nobet),
                 ("⚙️ Ayarlar", self._show_settings)]
        for i, (text, cmd) in enumerate(items):
            ctk.CTkButton(menu, text=text, command=cmd, fg_color=PANEL2, hover_color=CYAN, text_color=TEXT,
                          height=28, font=("Segoe UI", 11), anchor="w").grid(
                row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
        self.mode_desc = ctk.CTkLabel(bottom, text="", text_color=MUTED, font=("Segoe UI", 10),
                                      wraplength=200, justify="left")
        self.mode_desc.pack(side="bottom", padx=12, pady=(2, 6))
        self.mode_var = ctk.StringVar(value=self.mode_key)
        self._mode_labels = {k: i18n.tr(self.cfg["modes"][k]["label"]) for k in MODE_KEYS}
        self.mode_seg = ctk.CTkSegmentedButton(
            bottom, values=list(self._mode_labels.values()), selected_color=self._accent(),
            selected_hover_color=self._accent_hover(),
            unselected_color=PANEL2, font=("Segoe UI", 10), command=self._on_mode_seg)
        self.mode_seg.set(self._mode_labels[self.mode_key])
        self.mode_seg.pack(side="bottom", fill="x", padx=12)
        ctk.CTkLabel(bottom, text="MOD", text_color=MUTED, font=(FONT_MONO, 10)).pack(side="bottom")

        ctk.CTkLabel(p, text="SOHBETLER", text_color=MUTED, font=(FONT_MONO, 10), anchor="w").pack(
            fill="x", padx=14, pady=(4, 0))
        self.sessions_frame = ctk.CTkScrollableFrame(p, fg_color="transparent", corner_radius=0)
        self.sessions_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._update_mode_desc()
        self._refresh_sessions()

    def _on_mode_seg(self, label):
        key = {v: k for k, v in self._mode_labels.items()}.get(label, "normal")
        self.mode_var.set(key)
        self._on_mode_change()

    # ---------------- MOD RENGİ ----------------
    def _accent(self):
        return MODE_ACCENT.get(self.mode_key, MODE_ACCENT["normal"])["base"]

    def _accent_light(self):
        return MODE_ACCENT.get(self.mode_key, MODE_ACCENT["normal"])["light"]

    def _accent_hover(self):
        return MODE_ACCENT.get(self.mode_key, MODE_ACCENT["normal"])["hover"]

    def _apply_mode_theme(self):
        """Mod değiştiğinde canlı gösterge renklerini (küre hariç, o her karede kendi okur) günceller."""
        accent, light, hover = self._accent(), self._accent_light(), self._accent_hover()
        _THEME.update(base=accent, hover=hover)
        try:
            if hasattr(self, "brand_label"):
                self.brand_label.configure(text_color=accent)
            if hasattr(self, "mode_seg"):
                self.mode_seg.configure(selected_color=accent, selected_hover_color=hover)
            if hasattr(self, "mic_btn"):
                self.mic_btn.configure(hover_color=accent)
            if hasattr(self, "send_btn"):
                self.send_btn.configure(fg_color=accent, hover_color=hover)
            if hasattr(self, "confirm_ok_btn"):
                self.confirm_ok_btn.configure(fg_color=accent, hover_color=hover)
            if hasattr(self, "chat"):
                self.chat.tag_config("fenix", foreground=accent)
                self.chat._textbox.tag_config("fenix_lbl", foreground=accent)
            if hasattr(self, "pipe_bar"):
                self.pipe_bar.configure(progress_color=accent)
            if hasattr(self, "pipe_stage") and not self._pipe["active"]:
                cur = self.pipe_stage.cget("text")
                if cur and not cur.startswith(("✗", "⏹")):
                    self.pipe_stage.configure(text_color=accent)
            if hasattr(self, "pipe_title") and self.pipe_expanded:
                self.pipe_title.configure(text_color=accent)
            if hasattr(self, "new_chat_btn"):
                self.new_chat_btn.configure(fg_color=accent, hover_color=hover)
            if hasattr(self, "tts_switch"):
                self.tts_switch.configure(progress_color=accent)
            if hasattr(self, "voice_btn"):
                self._refresh_voice_btn()
            if hasattr(self, "sessions_frame"):
                self._refresh_sessions()
            self._pipe_render()
        except Exception as e:
            print(f"[MOD RENGİ HATASI] {e}")

    # ---------------- SOHBETLER ----------------
    def _refresh_sessions(self):
        for w in self.sessions_frame.winfo_children():
            w.destroy()
        q = self.session_search.get().strip() if hasattr(self, "session_search") else ""
        today = datetime.date.today()
        groups = {}
        order = ["Bugün", "Dün", "Önceki 7 gün", "Bu ay", "Daha eski"]
        for sess in self.memory.list_sessions(limit=150, query=q):
            try:
                d = datetime.date.fromisoformat((sess["updated"] or "")[:10])
            except ValueError:
                d = today
            delta = (today - d).days
            g = ("Bugün" if delta <= 0 else "Dün" if delta == 1 else "Önceki 7 gün" if delta <= 7
                 else "Bu ay" if d.month == today.month and d.year == today.year else "Daha eski")
            groups.setdefault(g, []).append(sess)
        if not groups:
            ctk.CTkLabel(self.sessions_frame, text="Henüz sohbet yok." if not q else "Sonuç yok.",
                         text_color=MUTED, font=("Segoe UI", 11)).pack(pady=8)
        for g in order:
            if g not in groups:
                continue
            ctk.CTkLabel(self.sessions_frame, text=g, text_color=MUTED, font=("Segoe UI", 10),
                         anchor="w").pack(fill="x", padx=6, pady=(6, 0))
            for sess in groups[g]:
                active = sess["id"] == self.session_id
                title = sess["title"] if len(sess["title"]) <= 28 else sess["title"][:27] + "…"
                b = ctk.CTkButton(self.sessions_frame, text=title, anchor="w", height=28, font=("Segoe UI", 11),
                                  fg_color=self._accent() if active else "transparent",
                                  hover_color=self._accent_light() if active else PANEL2,     # seçili olan üzerine gelince açılır, kararmaz
                                  text_color=BG if active else TEXT,
                                  command=lambda i=sess["id"]: self._open_session(i))
                b.pack(fill="x", padx=2, pady=1)
                b.bind("<Button-3>", lambda e, i=sess["id"]: self._session_menu(e, i))

    def _session_menu(self, event, sid):
        import tkinter as tk
        m = tk.Menu(self, tearoff=0, bg=PANEL2, fg=TEXT, activebackground=_THEME['base'], activeforeground=BG)
        m.add_command(label="✏️  Yeniden adlandır", command=lambda: self._rename_session(sid))
        m.add_command(label="🗑  Sil", command=lambda: self._delete_session(sid))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _rename_session(self, sid):
        sess = self.memory.get_session(sid)
        if not sess:
            return
        dlg = ctk.CTkInputDialog(text=f"Yeni ad (şu an: {sess['title']})", title="Sohbeti adlandır")
        name = dlg.get_input()
        if name and name.strip():
            self.memory.rename_session(sid, name.strip())
            self._refresh_sessions()
            if sid == self.session_id:
                self._set_chat_title(name.strip())

    def _delete_session(self, sid):
        from tkinter import messagebox
        sess = self.memory.get_session(sid)
        if not sess or not messagebox.askyesno("Sohbeti sil", f"“{sess['title']}” sohbeti ve mesajları silinsin mi?",
                                               parent=self):
            return
        self.memory.delete_session(sid)
        if sid == self.session_id:
            self._new_chat()
        else:
            self._refresh_sessions()

    def _capture_screen_hidden(self):
        """Ekran görüntüsünü FENIX pencereleri bir anlığına gizlenmiş halde alır (kendi penceresini görmesin).
        Worker thread'den çağrılır."""
        from modules import screen_capture as sc
        _scr = self.cfg.get("screen") or {}
        if not _scr.get("hide_fenix", _scr.get("hide_jarvis", True)):
            return sc.capture_screen_base64()
        hidden = threading.Event()
        self.ui_queue.put(("hide_for_capture", hidden))
        hidden.wait(2.0)
        time.sleep(0.35)                     # pencere kapanma animasyonu bitsin
        try:
            return sc.capture_screen_base64()
        finally:
            self.ui_queue.put(("restore_after_capture", None))

    # ---------------- GÜVENLİK BEKÇİSİ (v5.7.2) ----------------
    def _security_watch_loop(self):
        """Açılışta otomatik başlayan programları arka planda izler. Yeni ya da komutu değişmiş bir girdi görürse
        bir kez uyarır. Hiçbir şeyi kendisi değiştirmez; kaldırma, kullanıcı isterse onaylı yapılır.
        config.yaml -> security.startup_watch_minutes (0 = kapalı, varsayılan 30)."""
        try:
            minutes = float((self.cfg.get("security") or {}).get("startup_watch_minutes", 30))
        except Exception:
            minutes = 30.0
        if minutes <= 0:
            return
        time.sleep(90)          # açılış yükü bitsin; yeniden başlatma sırasında eklenenler ilk turda yakalanır
        alerted = set()
        while True:
            try:
                ch = fx.startup_changes()
                fresh = [e for e in ch["yeni"] + ch["degisen"]
                         if (fx.startup_entry_key(e), e["komut"]) not in alerted]
                if fresh:
                    alerted.update((fx.startup_entry_key(e), e["komut"]) for e in fresh)
                    self._security_alert(fresh)
            except Exception as e:
                print(f"[GÜVENLİK BEKÇİSİ] {e}")
            time.sleep(max(60.0, minutes * 60))

    def _window_in_front(self):
        """FENIX penceresi şu an önde ve odakta mı? (simge durumunda ya da başka pencere öndeyse False)"""
        try:
            if self.state() in ("iconic", "withdrawn"):
                return False
            return self.focus_displayof() is not None
        except Exception:
            return False

    def _security_alert(self, entries):
        """Worker thread'den çağrılır: uyarıyı sohbete yazar, açık sohbet varsa hafızaya da ekler
        (böylece 'ben kurdum' / 'kaldır' cevabını FENIX bağlamıyla anlar)."""
        lines = ["🛡 Güvenlik bekçisi: açılışta otomatik başlayan programlarda değişiklik var."]
        for e in entries[:6]:
            tag = "komutu değişti" if "onceki_komut" in e else "yeni eklendi"
            lines.append(f"  • {e['ad']} ({tag}): {e['komut'][:120]}")
        if len(entries) > 6:
            lines.append(f"  • ... ve {len(entries) - 6} tane daha")
        lines.append("Sen kurduysan 'başlangıç değişikliklerini onayla' de. Tanımıyorsan "
                     "'<ad> programını başlangıçtan kaldır' de (onay sorarım, yedeğini alırım).")
        text = "\n".join(lines)
        names = ", ".join(e["ad"] for e in entries[:3]) + (f" ve {len(entries) - 3} tane daha" if len(entries) > 3 else "")
        short = (f"Açılışta başlayan programlarda değişiklik: {names}. "
                 "Sen kurmadıysan FENIX'i açıp ayrıntıya bak.")
        self.ui_queue.put(("security_alert", (text, short)))
        try:
            self.memory.log_event("security", "Başlangıç değişikliği: " + ", ".join(e["ad"] for e in entries[:6]))
        except Exception:
            pass
        if self.session_id:
            self._remember("assistant", text, self.session_id)

    # ---------------- HATIRLATICI ----------------
    def _reminder_loop(self):
        while True:
            try:
                for r in self.reminders.due_now():
                    if r["id"] not in self._reminders_shown:
                        self._reminders_shown.add(r["id"])
                        missed = r["due"] < self._app_started - datetime.timedelta(minutes=1)
                        self.ui_queue.put(("reminder_due", (r, missed)))
            except Exception as e:
                print(f"[HATIRLATICI] {e}")
            time.sleep(10)

    def _command_training_loop(self):
        """v5.9.0: açılıştan kısa süre sonra bilgisayar envanteri eskiyse tazelenir ve eksik araçların söylenişleri
        (yalnızca Groq hızlı modeliyle, Gemini kotası harcanmadan) üretilir. Sınıra takılırsa 3 saat sonra yeniden
        denenir; hepsi bitince durur. config.yaml -> komut_hafizasi: {etkin, otomatik_egitim}."""
        cfg = self.cfg.get("komut_hafizasi") or {}
        if not cfg.get("etkin", True) or not cfg.get("otomatik_egitim", True) or not getattr(self.llm, "groq_api_key", ""):
            return
        time.sleep(30)
        mode_cfg = self.cfg["modes"]["normal"]
        while True:
            try:
                res = self.agent.train_commands(mode_cfg, background=True)
                if res["eklenen"]:
                    self.ui_queue.put(("pipeline_note", f"Komut hafızası: {res['eklenen']} yeni söyleniş öğrendi"))
                if not res["kalan"]:
                    return
            except Exception as e:
                print(f"[KOMUT HAFIZASI] eğitim: {e}")
            time.sleep(3 * 3600)

    def _show_reminder_popup(self, r, missed):
        when = human_when(r["due"])
        self._append_chat("sys", f"⏰ Hatırlatma{' (kaçırılan, ' + when + ')' if missed else ''}: {r['text']}")
        try:
            audio_io.speak(f"Hatırlatma: {r['text']}", self.cfg["audio"].get("tts_voice", "tr-TR-AhmetNeural"))
        except Exception:
            pass
        win = ctk.CTkToplevel(self)
        win.title("FENIX • Hatırlatma")
        win.geometry("420x220")
        win.configure(fg_color=BG)
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="⏰ Hatırlatma" + (" (kaçırılan)" if missed else ""), text_color=AMBER,
                     font=(FONT_HEAD, 16, "bold")).pack(pady=(18, 6))
        ctk.CTkLabel(win, text=r["text"], text_color=TEXT, font=("Segoe UI", 14), wraplength=380).pack(padx=16)
        ctk.CTkLabel(win, text=when, text_color=MUTED, font=("Segoe UI", 11)).pack(pady=(4, 10))
        bar = ctk.CTkFrame(win, fg_color="transparent")
        bar.pack(pady=(0, 14))

        def done():
            self.reminders.mark_done(r["id"])
            win.destroy()
            self._refresh_reminders_window()

        def snooze():
            self.reminders.snooze(r["id"], 10)
            self._reminders_shown.discard(r["id"])
            win.destroy()
            self._append_chat("sys", f"⏰ '{r['text']}' 10 dakika ertelendi.")
            self._refresh_reminders_window()

        ctk.CTkButton(bar, text="✓ Tamam", width=120, fg_color=_THEME['base'], hover_color=_THEME['hover'], command=done).pack(
            side="left", padx=6)
        ctk.CTkButton(bar, text="⏱ 10 dk ertele", width=130, fg_color=PANEL2, hover_color=CYAN,
                      command=snooze).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", done)
        try:
            win.lift()
            win.focus_force()
        except Exception:
            pass

    def _refresh_reminders_window(self):
        win = self._windows.get("reminders")
        if win is not None and win.winfo_exists():
            win.refresh()

    def _show_reminders(self):
        win = self._open_window("reminders", lambda: RemindersWindow(self))
        try:
            win.refresh()
        except Exception:
            pass

    def _notify_history_session(self):
        win = self._windows.get("history")
        if win is not None and win.winfo_exists():
            win.on_session_changed()

    def _set_chat_title(self, title):
        self.chat_title.configure(text=title if len(title) <= 34 else title[:33] + "…")

    def _clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def _new_chat(self, incognito=False):
        """Yeni (boş) sohbet. Veritabanına ilk mesaj gönderilince kaydedilir (boş sohbetler birikmesin).
        incognito=True: gizli sohbet; mesajlar hiçbir yere kaydedilmez, kapatınca kaybolur."""
        self.session_id = None
        self.memory.current_session_id = None
        self.memory.set_incognito(incognito)
        self.llm.reset_mode_session()
        self._clear_chat()
        if incognito:
            self._set_chat_title("🕶 Gizli sohbet")
            self._append_chat("sys", "🕶 Gizli sohbet: mesajlar, yapılanlar ve başlık kaydedilmez; sohbet listesinde "
                                     "görünmez. Yeni sohbet açınca ya da FENIX'i kapatınca silinir. "
                                     "(FENIX önceki hafızasını yine kullanabilir.)")
        else:
            self._set_chat_title("Yeni sohbet")
            self._append_chat("sys", "Yeni sohbet. Mod: " + self.cfg["modes"][self.mode_key]["label"] +
                              f"  •  Bas-Konuş: buton ya da '{self.cfg['audio']['ptt_key']}'.")
        self._refresh_sessions()
        self._notify_history_session()
        try:
            self.entry.focus_set()
        except Exception:
            pass

    def _open_session(self, sid):
        sess = self.memory.get_session(sid)
        if not sess:
            return
        self.session_id = sid
        self.memory.current_session_id = sid
        self.memory.set_incognito(False)
        self.llm.reset_mode_session()          # model oturumu sıfırlanır; bağlam bu sohbetin mesajlarından gelir
        self._clear_chat()
        self._set_chat_title(sess["title"])
        msgs = self.memory.get_session_messages(sid)
        last_day = None
        for ts, role, content in msgs:
            day = ts[:10]
            if day != last_day:
                try:
                    label = datetime.date.fromisoformat(day).strftime("%d.%m.%Y")
                except ValueError:
                    label = day
                self._append_chat("sys", f"— {label} —")
                last_day = day
            self._append_chat("user" if role == "user" else "fenix", content)
        if not msgs:
            self._append_chat("sys", "Bu sohbette henüz mesaj yok.")
        self._refresh_sessions()
        self._notify_history_session()

    def _ensure_session(self):
        """İlk mesajda sohbeti oluşturur (gizli sohbette oluşturmaz)."""
        if self.memory.incognito:
            return None
        if self.session_id is None:
            self.session_id = self.memory.create_session(self.mode_key)
            self.memory.current_session_id = self.session_id
            self._refresh_sessions()
            self._notify_history_session()
        return self.session_id

    def _auto_title(self, sid):
        """Sohbetin konusuna göre kısa başlık (arka planda, hızlı model).
        İlk cevaptan sonra verilir; sohbet 6 mesaja ulaşınca konu netleştiği için bir kez daha gözden geçirilir.
        Kullanıcı elle adlandırdıysa hiç dokunulmaz."""
        try:
            sess = self.memory.get_session(sid)
            if not sess or sess["auto_titled"] == 2:
                return
            msgs = self.memory.get_session_messages(sid, limit=12)
            if not msgs or (sess["auto_titled"] == 1 and len(msgs) != 6):
                return
            convo = "\n".join(f"{'Kullanıcı' if r == 'user' else 'FENIX'}: {c[:300]}" for _, r, c in msgs[:8])
            title = ""
            try:
                title = self.llm.complete(self.cfg["modes"][self.mode_key], (
                    "Aşağıdaki sohbete konusunu anlatan 2-5 kelimelik kısa bir Türkçe başlık ver. Sadece başlığı "
                    "yaz; tırnak, nokta, emoji kullanma.\n\n" + convo), fast=True,
                    fast_model=(self.cfg.get("deep_research") or {}).get("fast_model", "openai/gpt-oss-20b"))
            except Exception as e:
                print(f"[BAŞLIK] model başlık veremedi: {e}")
            title = re.sub(r"[\"'`*#\n]+", " ", (title or "")).strip(" .:-")[:60]
            if not title or len(title) < 3:
                first = next((c for _, r, c in msgs if r == "user"), "Sohbet")
                title = " ".join(re.sub(r"\s+", " ", first).split()[:6])[:60] or "Sohbet"
            self.memory.rename_session(sid, title, auto=True)
            self.ui_queue.put(("session_titled", (sid, title)))
        except Exception as e:
            print(f"[BAŞLIK] {e}")

    # ---------------- PIPELINE ----------------
    def _build_pipeline(self):
        self.pipe = ctk.CTkFrame(self, width=40, fg_color=PANEL2, corner_radius=0)
        self.pipe.grid(row=0, column=1, sticky="nsew")
        self.pipe.grid_propagate(False)
        self.pipe_expanded = False

        self.pipe_title = ctk.CTkLabel(self.pipe, text="●", text_color=MUTED, font=("Segoe UI", 16),
                                       cursor="hand2")
        self.pipe_title.pack(pady=(14, 0))
        self.pipe_title.bind("<Button-1>", lambda e: self._toggle_pipeline())
        self.pipe_hint = ctk.CTkLabel(self.pipe, text="", text_color=MUTED, font=("Segoe UI", 9))
        self.pipe_hint.pack(pady=(0, 6))

        self.pipe_body = ctk.CTkFrame(self.pipe, fg_color="transparent")
        self.pipe_stage = ctk.CTkLabel(self.pipe_body, text="", text_color=self._accent(),
                                       font=(FONT_HEAD, 12, "bold"), wraplength=180)
        self.pipe_stage.pack(pady=(6, 6), padx=10)
        self.pipe_steps_frame = ctk.CTkFrame(self.pipe_body, fg_color="transparent")
        self.pipe_steps_frame.pack(fill="x", padx=12)
        self.pipe_bar = ctk.CTkProgressBar(self.pipe_body, progress_color=self._accent(), width=180)
        self.pipe_bar.set(0)
        self.pipe_bar.pack(pady=(10, 2), padx=10)
        self.pipe_info = ctk.CTkLabel(self.pipe_body, text="", text_color=MUTED, font=("Consolas", 10))
        self.pipe_info.pack(pady=(0, 6))
        self.pipe_stop = ctk.CTkButton(self.pipe_body, text="⏹ Görevi durdur", width=170, height=28,
                                       fg_color="#7f1d1d", hover_color="#b91c1c", text_color=TEXT,
                                       command=self._cancel_task)
        self.pipe_stop.pack(pady=(0, 4))
        self.pipe_log = ctk.CTkTextbox(self.pipe_body, height=140, width=180, fg_color=BG,
                                       text_color=MUTED, font=("Consolas", 10))
        self.pipe_log.pack(pady=6, padx=10, fill="both", expand=True)

    def _expand_pipeline(self, expand=True):
        if expand and not self.pipe_expanded:
            self.pipe.configure(width=230)
            self.pipe_title.configure(text="GÖREV  ◂", text_color=self._accent(), font=(FONT_HEAD, 12, "bold"))
            self.pipe_hint.configure(text="gizlemek için başlığa tıkla")
            self.pipe_body.pack(fill="both", expand=True)
            self.pipe_expanded = True
        elif not expand and self.pipe_expanded:
            self.pipe_body.pack_forget()
            self.pipe.configure(width=40)
            self.pipe_title.configure(text="▸" if self._pipe["steps"] else "●", text_color=MUTED,
                                      font=("Segoe UI", 16))
            self.pipe_hint.configure(text="")
            self.pipe_expanded = False

    def _toggle_pipeline(self):
        """Başlığa tıklayınca paneli aç/kapa (son görevin kaydı kaybolmaz)."""
        self._expand_pipeline(not self.pipe_expanded)

    def _pipe_make_label(self, name):
        lbl = ctk.CTkLabel(self.pipe_steps_frame, text=f"○ {name}", text_color=MUTED,
                           font=("Segoe UI", 11), anchor="w", justify="left", wraplength=170)
        lbl.pack(fill="x", pady=1)
        self._pipe["labels"].append(lbl)

    def _pipe_render(self):
        """Adım etiketlerini duruma göre boyar: ✓ biten, ▶ şu anki, ○ bekleyen."""
        p = self._pipe
        accent, light = self._accent(), self._accent_light()
        for i, (name, lbl) in enumerate(zip(p["steps"], p["labels"])):
            if not p["active"] and p["idx"] >= len(p["steps"]):
                lbl.configure(text=f"✓ {name}", text_color=accent)
            elif i < p["idx"]:
                lbl.configure(text=f"✓ {name}", text_color=accent)
            elif i == p["idx"]:
                lbl.configure(text=f"▶ {name}", text_color=light)
            else:
                lbl.configure(text=f"○ {name}", text_color=MUTED)

    def _set_stop_enabled(self, on):
        self.pipe_stop.configure(state="normal" if on else "disabled", fg_color="#7f1d1d" if on else PANEL)
        try:
            self.after(50, self._refresh_voice_btn)      # üstteki Durdur da görev boyunca etkin olsun
        except Exception:
            pass

    def _on_plan(self, steps):
        self._set_stop_enabled(True)
        p = self._pipe
        for lbl in p["labels"]:
            lbl.destroy()
        p.update(steps=[], labels=[], idx=-1, active=True, start=time.time(),
                 stage_start=time.time(), shown=0.0)
        p["gen"] += 1                      # bekleyen "kapan" zamanlayıcılarını geçersiz kıl
        for name in steps:
            p["steps"].append(name)
            self._pipe_make_label(name)
        self.pipe_bar.set(0)
        self.pipe_log.delete("1.0", "end")
        task = (p.get("task") or "").strip()
        if task:
            self.pipe_log.insert("end", f"GÖREV: {task[:160]}\n")
        self.pipe_log.insert("end", f"başladı: {datetime.datetime.now():%H:%M:%S}\n\n")
        self.pipe_stage.configure(text="Başlıyor...", text_color=self._accent())
        self._expand_pipeline(True)
        self._pipe_render()

    def _on_stage(self, name):
        p = self._pipe
        if not p["active"]:
            self._on_plan([name])
        if name not in p["steps"]:
            p["steps"].append(name)
            self._pipe_make_label(name)
        p["idx"] = p["steps"].index(name)
        p["stage_start"] = time.time()
        p["shown"] = max(p["shown"], p["idx"] / max(len(p["steps"]), 1))
        self.pipe_stage.configure(text=name, text_color=self._accent())
        self._pipe_render()

    def _cancel_task(self):
        """Görevi durdurur: derin araştırma bir sonraki adımda, model beklemeleri yarım saniye içinde kesilir."""
        self._cancel_event.set()
        self.pipe_stage.configure(text="Durduruluyor...", text_color=AMBER)
        self._set_stop_enabled(False)

    def _on_finish(self, ok):
        """Görev bitti. Panel KAPANMAZ: durum, süre ve kayıt yerinde kalır; yeni görevde yenilenir."""
        self._set_stop_enabled(False)
        p = self._pipe
        if not p["steps"]:
            self._on_plan(["İşlem"])
        was_active = p["active"]
        p["active"] = False
        p["gen"] += 1
        cancelled = self._cancel_event.is_set()
        if ok and not cancelled:
            p["idx"] = len(p["steps"])       # hepsi ✓
            self._pipe_render()
            self.pipe_bar.set(1.0)
            state, color, word = "✓ Tamamlandı", self._accent(), "tamamlandı"
        else:
            if 0 <= p["idx"] < len(p["labels"]):
                p["labels"][p["idx"]].configure(text=f"✗ {p['steps'][p['idx']]}",
                                                text_color=AMBER if cancelled else "#ef4444")
            state, color, word = (("⏹ Durduruldu", AMBER, "durduruldu") if cancelled
                                  else ("✗ Hata oluştu", "#ef4444", "hata"))
        self.pipe_stage.configure(text=state, text_color=color)
        if was_active:
            elapsed = time.time() - p["start"]
            dur = f"{elapsed:.1f} sn" if elapsed < 60 else f"{int(elapsed // 60)} dk {int(elapsed % 60)} sn"
            self.pipe_info.configure(text=f"{word}  •  {dur}  •  {datetime.datetime.now():%H:%M}")
            self.pipe_log.insert("end", f"\n— {word}: {dur} —\n")
            self.pipe_log.see("end")

    def _pipe_tick(self):
        """Her karede: aktif adımı nabız gibi yak, çubuğu yavaşça ilerlet (takılı kalmış gibi görünmesin)."""
        p = self._pipe
        if not p["active"] or not p["steps"]:
            return
        n = len(p["steps"])
        now = time.time()
        # Çubuk, her adımın kendi dilimi içinde yavaşça ilerler (τ=10 sn): uzun süren bir adımda
        # bile hareket etmeye devam eder, ama dilimi asla doldurmaz (bitiş sinyali 100% yapar).
        if p["idx"] >= 0:
            t_step = now - p["stage_start"]
            target = (p["idx"] + 0.95 * (1 - math.exp(-t_step / 10.0))) / n
        else:
            target = 0.02
        p["shown"] = max(p["shown"], target)
        self.pipe_bar.set(min(p["shown"], 0.99))
        # Sahte yüzde yerine gerçek bilgi: kaçıncı adım + geçen süre
        step_no = max(p["idx"], 0) + 1
        self.pipe_info.configure(text=f"adım {min(step_no, n)}/{n}  •  {now - p['start']:.0f} sn")
        # nabız
        if 0 <= p["idx"] < len(p["labels"]):
            pulse = self._accent() if int((now - p["start"]) * 2) % 2 == 0 else self._accent_light()
            p["labels"][p["idx"]].configure(text_color=pulse)

    # ---------------- MERKEZ / SAĞ ----------------
    def _build_center(self):
        c = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        c.grid(row=0, column=2, sticky="nsew")
        c.grid_rowconfigure(0, weight=1)
        c.grid_columnconfigure(0, weight=1)

        self.canvas = ctk.CTkCanvas(c, bg=BG, highlightthickness=0, width=380, height=380)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda e: self._draw_grid())

        self.mic_btn = ctk.CTkButton(c, text="🎤  Bas-Konuş", fg_color=PANEL, hover_color=self._accent(),
                                     text_color=TEXT, height=48, width=200, font=(FONT_HEAD, 14, "bold"),
                                     command=self._toggle_mic)
        self.mic_btn.grid(row=1, column=0, pady=(0, 8))
        self.status_label = ctk.CTkLabel(c, text="Hazır", text_color=MUTED, font=(FONT_MONO, 12))
        self.status_label.grid(row=2, column=0, pady=(0, 14))

    def _build_right(self):
        r = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        r.grid(row=0, column=3, sticky="nsew")
        self._right_panel = r
        # Sohbet genişliği: sol kenardaki ince ayraç sürüklenir, genişlik hatırlanır
        sash = ctk.CTkFrame(r, width=6, fg_color=PANEL2, corner_radius=0, cursor="sb_h_double_arrow")
        sash.place(x=0, y=0, relheight=1)
        sash.bind("<B1-Motion>", self._drag_chat_sash)
        sash.bind("<ButtonRelease-1>", lambda e: user_settings.set("chat_width", getattr(self, "_chat_width", None)))
        sash.bind("<Enter>", lambda e: sash.configure(fg_color=self._accent()))
        sash.bind("<Leave>", lambda e: sash.configure(fg_color=PANEL2))
        self._chat_sash = sash
        w = user_settings.get("chat_width")
        if isinstance(w, int) and w >= 360:
            self.after(50, lambda: self._set_chat_width(w))
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind_all(seq, lambda e: self._chat_zoom(+1))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind_all(seq, lambda e: self._chat_zoom(-1))
        r.grid_rowconfigure(1, weight=1)
        r.grid_columnconfigure(0, weight=1)

        # Ses araç çubuğu: okuma aç/kapa + okumayı durdur
        vb = ctk.CTkFrame(r, fg_color="transparent")
        vb.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        self.stop_btn = ctk.CTkButton(vb, text="⏹ Durdur", width=90, height=30, fg_color="#7f1d1d",
                                      hover_color="#b91c1c", text_color=TEXT, command=self._stop_speech)
        self.stop_btn.pack(side="right", padx=(6, 0))
        self.voice_btn = ctk.CTkButton(vb, text="", width=128, height=30, fg_color=PANEL2,
                                       hover_color=CYAN, text_color=TEXT, command=self._toggle_tts_button)
        self.voice_btn.pack(side="right")
        self.chat_hist_btn = ctk.CTkButton(vb, text="📜", width=34, height=30, fg_color=PANEL2, hover_color=CYAN,
                                           text_color=TEXT, command=self._show_chat_history)
        self.chat_hist_btn.pack(side="left", padx=(0, 6))
        self.chat_title = ctk.CTkLabel(vb, text="Yeni sohbet", text_color=TEXT, font=(FONT_HEAD, 14, "bold"),
                                       anchor="w")
        self.chat_title.pack(side="left", fill="x", expand=True)
        self.stop_btn.configure(state="disabled", fg_color=PANEL2)
        self._refresh_voice_btn()

        self._chat_font = int(user_settings.get("chat_font", 13) or 13)
        self.chat = ctk.CTkTextbox(r, fg_color=BG, text_color=TEXT, font=("Segoe UI", self._chat_font), wrap="word")
        i18n.mark_raw(self.chat)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.chat.configure(state="disabled")
        self.chat.tag_config("user", foreground=CYAN)
        self.chat.tag_config("fenix", foreground=self._accent())
        self.chat.tag_config("sys", foreground=MUTED)
        self.chat.tag_config("b", foreground="#ffffff")
        self.chat.tag_config("head", foreground=CYAN)
        # etiket satırları (CTkTextbox 'font' kabul etmez: alttaki Tk metin kutusuna verilir)
        self.chat._textbox.tag_config("user_lbl", foreground=MUTED, font=(FONT_MONO, 10), spacing1=6)
        self.chat._textbox.tag_config("fenix_lbl", foreground=self._accent(), font=(FONT_MONO, 10), spacing1=6)

        # Onay kutusu alanı (gizli, gerektiğinde belirir)
        self.confirm_frame = ctk.CTkFrame(r, fg_color=PANEL2)
        self.confirm_label = ctk.CTkLabel(self.confirm_frame, text="", text_color=AMBER,
                                          font=("Segoe UI", 12), wraplength=360, justify="left")
        self.confirm_label.pack(padx=10, pady=(10, 6))
        # Butonlar açıklamanın hemen altında: komut ne kadar uzun olursa olsun her zaman görünür kalır
        btns = ctk.CTkFrame(self.confirm_frame, fg_color="transparent")
        btns.pack(pady=(0, 8))
        # Ayrıntı (komutun tamamı vb.) sabit yükseklikte, kaydırılabilir kutuda
        self.confirm_detail = ctk.CTkTextbox(self.confirm_frame, height=120, fg_color=BG, text_color=MUTED,
                                             font=("Consolas", 11), wrap="word")
        self.confirm_ok_btn = ctk.CTkButton(btns, text="✓ Onayla", fg_color=self._accent(),
                                            hover_color=self._accent_hover(), width=120,
                                            command=lambda: self._resolve_confirm(True))
        self.confirm_ok_btn.pack(side="left", padx=6)
        ctk.CTkButton(btns, text="✗ Reddet", fg_color="#7f1d1d", hover_color="#b91c1c", width=120,
                      command=lambda: self._resolve_confirm(False)).pack(side="left", padx=6)

        bar = ctk.CTkFrame(r, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        bar.grid_columnconfigure(1, weight=1)
        # Ekli dosya çipleri (boşken gizli)
        self.chips = ctk.CTkFrame(bar, fg_color="transparent")
        self.attach_btn = ctk.CTkButton(bar, text="📎", width=46, height=46, fg_color=PANEL2, hover_color=CYAN,
                                        text_color=TEXT, font=("Segoe UI", 18), command=self._pick_files)
        self.attach_btn.grid(row=1, column=0, padx=(0, 6))
        # Çok satırlı giriş: Enter = gönder, Shift+Enter = alt satır, Ctrl+A/Z/Y çalışır
        self.entry = ctk.CTkTextbox(bar, fg_color=BG, text_color=TEXT, height=46, wrap="word",
                                    font=("Segoe UI", getattr(self, "_chat_font", 13)), undo=True)
        self.entry.grid(row=1, column=1, sticky="ew", padx=(0, 6))
        tb = self.entry._textbox
        tb.bind("<Return>", self._on_enter)
        tb.bind("<KP_Enter>", self._on_enter)
        tb.bind("<Shift-Return>", self._on_shift_enter)
        tb.bind("<Control-a>", self._select_all)
        tb.bind("<Control-A>", self._select_all)
        tb.bind("<Control-v>", self._on_paste)
        tb.bind("<Control-V>", self._on_paste)
        tb.bind("<KeyRelease>", lambda e: self._autosize_entry())
        tb.bind("<Control-BackSpace>", self._delete_word)
        tb.bind("<Control-Delete>", lambda e: self._delete_word(e, forward=True))
        self.send_btn = ctk.CTkButton(bar, text="Gönder", fg_color=self._accent(), hover_color=self._accent_hover(),
                                      width=80, height=46, command=self._send_text)
        self.send_btn.grid(row=1, column=2)
        hint = "Enter gönder  •  Shift+Enter alt satır  •  Ctrl+V görsel  •  📎" + (" / sürükle" if TkinterDnD else "")
        ctk.CTkLabel(bar, text=hint, text_color=MUTED, font=("Segoe UI", 10)).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self._append_chat("sys", "FENIX hazır. Yeni sohbet • Mod: " + self.cfg["modes"][self.mode_key]["label"] +
                          f"  •  Bas-Konuş: uygulama içi buton ya da '{self.cfg['audio']['ptt_key']}' tuşu.")

    # ---------------- ORB ANIMASYONU ----------------
    _ORB_BARS = 72

    @staticmethod
    def _mix(c1, c2, t):
        """İki rengi karıştırır (Tk'de saydamlık yok: soluk tonlar arka planla karıştırılarak elde edilir)."""
        a = [int(c1[k:k + 2], 16) for k in (1, 3, 5)]
        b = [int(c2[k:k + 2], 16) for k in (1, 3, 5)]
        return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))

    def _draw_grid(self):
        cv = self.canvas
        cv.delete("grid")
        w, h = int(cv.winfo_width()) or 380, int(cv.winfo_height()) or 380
        for x in range(0, w, 40):
            cv.create_line(x, 0, x, h, fill=GRID, tags="grid")
        for y in range(0, h, 40):
            cv.create_line(0, y, w, y, fill=GRID, tags="grid")
        cv.delete("hud")
        cv.create_text(18, 16, anchor="nw", text=i18n.tr("FENIX // ÇEKİRDEK"), fill=MUTED, font=(FONT_MONO, 9), tags="hud")
        cv.tag_lower("grid")

    def _draw_orb(self):
        """Holografik daire. Öğeler BİR KEZ oluşturulur, her karede yalnızca yerleri güncellenir (yazarken takılmaz).
        Boşta: yavaş nefes; dinlerken: çubuklar ses seviyesine göre; düşünürken: hızlı dalga."""
        cv = self.canvas
        w = int(cv.winfo_width()) or 380
        h = int(cv.winfo_height()) or 380
        cx, cy = w // 2, h // 2 - 10
        sc = max(0.75, min(1.35, min(w, h) / 420))
        self._orb_phase += 0.09
        if not getattr(self, "_orb_items", None):
            self._orb_outer = cv.create_oval(0, 0, 0, 0, width=1)
            self._orb_bars = [cv.create_line(0, 0, 0, 0, width=3, capstyle="round") for _ in range(self._ORB_BARS)]
            self._orb_dash = cv.create_oval(0, 0, 0, 0, width=1, dash=(3, 6))
            self._orb_ring = cv.create_oval(0, 0, 0, 0, width=2, fill=BG)
            self._orb_core = cv.create_oval(0, 0, 0, 0, width=0)
            self._orb_ticks = [cv.create_line(0, 0, 0, 0, width=1) for _ in range(2)]
            self._orb_items = True
            self._orb_style = None
            self._draw_grid()

        accent, light = self._accent(), self._accent_light()
        state = self._orb_state
        style = (accent, light, state)
        if style != self._orb_style:
            dim = self._mix(accent, BG, 0.78)
            cv.itemconfigure(self._orb_outer, outline=dim)
            cv.itemconfigure(self._orb_dash, outline=self._mix(accent, BG, 0.5))
            cv.itemconfigure(self._orb_ring, outline=accent)
            cv.itemconfigure(self._orb_core, fill=light if state == "listening" else accent)
            bar_col = light if state != "idle" else self._mix(accent, BG, 0.2)
            for it in self._orb_bars:
                cv.itemconfigure(it, fill=bar_col)
            for it in self._orb_ticks:
                cv.itemconfigure(it, fill=self._mix(accent, BG, 0.5))
            self._orb_style = style

        ph = self._orb_phase
        level = 0.0
        if state == "listening" and getattr(self, "recorder", None) is not None:
            level = min(1.0, getattr(self.recorder, "level", 0.0) * 4)
        r0 = 112 * sc
        n = self._ORB_BARS
        for i, it in enumerate(self._orb_bars):
            if state == "idle":
                ln = 6 + 10 * abs(math.sin(i * 0.55 + ph * 0.5))
            elif state == "listening":
                ln = 8 + (14 + 34 * level) * abs(math.sin(i * 0.9 + ph * 2.2))
            else:
                ln = 8 + 28 * abs(math.sin(i * 0.35 + ph * 3.0) * math.cos(i * 0.21 - ph))
            a = 2 * math.pi * i / n + ph * (0.05 if state == "idle" else 0.15)
            ca, sa = math.cos(a), math.sin(a)
            cv.coords(it, cx + r0 * ca, cy + r0 * sa, cx + (r0 + ln * sc) * ca, cy + (r0 + ln * sc) * sa)
        ro = 170 * sc
        cv.coords(self._orb_outer, cx - ro, cy - ro, cx + ro, cy + ro)
        rd = 96 * sc
        cv.coords(self._orb_dash, cx - rd, cy - rd, cx + rd, cy + rd)
        rr = 66 * sc
        cv.coords(self._orb_ring, cx - rr, cy - rr, cx + rr, cy + rr)
        pulse = {"idle": 2, "listening": 6, "thinking": 4}.get(state, 2)
        rc = (44 + pulse * math.sin(ph * (1 if state == "idle" else 3))) * sc
        cv.coords(self._orb_core, cx - rc, cy - rc, cx + rc, cy + rc)
        cv.coords(self._orb_ticks[0], cx - ro - 20 * sc, cy, cx - ro + 10 * sc, cy)
        cv.coords(self._orb_ticks[1], cx + ro - 10 * sc, cy, cx + ro + 20 * sc, cy)

    # ---------------- OLAY DÖNGÜSÜ ----------------
    def _tick(self):
        """Ana arayüz döngüsü. Herhangi bir parçadaki hata döngüyü ÖLDÜRMEMELİ (aksi halde arayüz
        donar), bu yüzden her parça ayrı korunur ve döngü her koşulda yeniden zamanlanır."""
        try:
            try:
                minimized = (self.state() == "iconic")
            except Exception:
                minimized = False
            if not minimized:            # simge durumundayken çizme: boşuna CPU harcama
                try:
                    self._draw_orb()
                except Exception as e:
                    print(f"[ORB HATASI] {e}")
                try:
                    self._pipe_tick()
                except Exception as e:
                    print(f"[PIPELINE HATASI] {e}")
            if getattr(self, "recorder", None) is not None and self.recorder._recording:
                lv = min(1.0, self.recorder.level * 4)          # konuşma genelde tepe değerin ~%25'i altında
                bars = int(round(lv * 10))
                self.status_label.configure(text=f"Dinliyorum  {'▮' * bars}{'▯' * (10 - bars)}   "
                                                 f"({self.recorder.device_name[:28]})")
            self._gc_counter += 1
            if self._gc_counter % 75 == 0:          # ~3 sn'de bir, ana iş parçacığında
                gc.collect(0 if self._gc_counter % 750 else 2)
            try:
                self._voice_poll = getattr(self, "_voice_poll", 0) + 1
                if self._voice_poll % 10 == 0:
                    self._refresh_voice_btn()
            except Exception as e:
                print(f"[SES BUTONU HATASI] {e}")
            # Kuyruktaki olayları işle; tek bir bozuk olay diğerlerini engellemesin
            while True:
                try:
                    kind, data = self.ui_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._handle_ui_event(kind, data)
                except Exception as e:
                    print(f"[UI OLAY HATASI] {kind}: {e}")
        finally:
            self.after(40 if self._orb_state != "idle" else 66, self._tick)    # boşta ~15 FPS, meşgulken ~25 FPS

    def _handle_ui_event(self, kind, data):
        if kind == "chat":
            who, text = data
            self._append_chat(who, text)
        elif kind == "status":
            self.status_label.configure(text=data)
        elif kind == "orb":
            self._orb_state = data
        elif kind == "plan":
            self._on_plan(data)
        elif kind == "stage":
            self._on_stage(data)
        elif kind == "finish":
            self._on_finish(data)
        elif kind == "waiting":
            self.pipe_stage.configure(text="⏳ Onay bekleniyor", text_color=AMBER)
            self.pipe_log.insert("end", "• onay bekleniyor (sağ alttaki kutu)\n")
            self.pipe_log.see("end")
        elif kind == "pipeline_note":
            self.pipe_log.insert("end", f"• {data}\n")
            self.pipe_log.see("end")
        elif kind == "confirm_show":
            title, message, detail = data
            self._show_confirm_box(title, message, detail)
        elif kind == "load":
            self.load_label.configure(text=data)
        elif kind == "process":
            self._process_input(data)
        elif kind == "hide_confirm":
            self._hide_confirm_box()
        elif kind == "hide_for_capture":
            self._hidden_wins = [w for w in self._windows.values() if w is not None and w.winfo_exists()
                                 and w.state() != "withdrawn"]
            for w in self._hidden_wins:
                w.withdraw()
            self.withdraw()
            self.update_idletasks()
            data.set()
        elif kind == "restore_after_capture":
            self.deiconify()
            for w in getattr(self, "_hidden_wins", []):
                try:
                    w.deiconify()
                except Exception:
                    pass
            self._hidden_wins = []
            self.lift()
        elif kind == "reminder_due":
            r, missed = data
            self._show_reminder_popup(r, missed)
        elif kind == "security_alert":
            text, short = data
            self._append_chat("sys", text)
            # FENIX penceresi önde değilse (arkada / simge durumunda) Windows bildirimi de göster
            if (self.cfg.get("security") or {}).get("windows_notifications", True) and not self._window_in_front():
                notifier.show_toast_async("FENIX · Güvenlik bekçisi", short)
            self.pipe_log.insert("end", "• güvenlik bekçisi: başlangıç değişikliği\n")
            self.pipe_log.see("end")
            voice = self.cfg["audio"].get("tts_voice", "tr-TR-AhmetNeural")
            threading.Thread(target=lambda: audio_io.speak(
                "Açılışta başlayan programlarda yeni bir değişiklik var, ayrıntıyı sohbete yazdım.", voice),
                daemon=True).start()
        elif kind == "gozcu_alert":
            ev = data
            self._append_chat("sys", f"🛡 {ev['baslik']}\n{ev['metin']}")
            if (self.cfg.get("security") or {}).get("windows_notifications", True) and not self._window_in_front():
                notifier.show_toast_async("FENIX · " + ev["baslik"], ev["kisa"])
            self.pipe_log.insert("end", f"• nöbet/bekçi: {ev.get('kaynak', '')}\n")
            self.pipe_log.see("end")
            try:
                self.memory.log_event("security", f"{ev['baslik']}: {ev['kisa']}"[:300])
            except Exception:
                pass
            if nobet.should_speak(self._nobet_cfg.get("uyari_sesi", "onemli"), ev["seviye"],
                                  nobet.quiet_now(self._nobet_cfg.get("sessiz_saat"))):
                voice = self.cfg["audio"].get("tts_voice", "tr-TR-AhmetNeural")
                threading.Thread(target=lambda: audio_io.speak(ev["kisa"], voice), daemon=True).start()
        elif kind == "answer":
            sid, text = data[0], data[1]
            sure = data[2] if len(data) > 2 else None
            self._notify_answer(text)
            if sid is None or sid == self.session_id:
                self._append_chat("fenix", text, sure=sure)
            else:
                sess = self.memory.get_session(sid)
                self._append_chat("sys", f"“{sess['title'] if sess else 'Önceki sohbet'}” sohbetindeki cevap hazır "
                                         "(soldan açabilirsin).")
            self._refresh_sessions()
        elif kind == "session_titled":
            sid, title = data
            if sid == self.session_id:
                self._set_chat_title(title)
            self._refresh_sessions()
        elif kind == "attach_ok":
            self._attachments.append(data)
            self._render_chips()
            self.status_label.configure(text="Hazır")
            if data.get("note"):
                self._append_chat("sys", f"⚠️ {data['name']}: {data['note']}")
        elif kind == "attach_err":
            name, msg = data
            self.status_label.configure(text="Hazır")
            self._append_chat("sys", f"⚠️ {name} eklenemedi: {msg}")
        elif kind == "report":
            self._show_reports(data)
        elif kind == "history_refresh":
            win = self._windows.get("history")
            if win is not None and win.winfo_exists():
                win.refresh()

    # ---------------- CHAT ----------------
    def _append_chat(self, who, text, sure=None):
        self.chat.configure(state="normal")
        if who in ("user", "fenix"):
            label = "> " + (i18n.tr("Sen").upper() if who == "user" else "FENIX")
            if who == "fenix" and sure is not None:      # cevap süresi (07.11 isteği): hız ölçümü için
                label += f"  ·  {sure:.1f} sn" if sure < 60 else f"  ·  {int(sure // 60)} dk {int(sure % 60)} sn"
            self.chat.insert("end", f"\n{label}\n", who + "_lbl")
        else:
            self.chat.insert("end", "\n• ", who)
        if who == "sys":
            text = i18n.tr(text)
        elif who == "fenix":
            text = i18n.tr(text, lines=False)      # yalnız sabit cevaplar (LLM cevabı sözlükte yoktur)
        self._insert_rich(text, plain=(who == "user"))
        self.chat.insert("end", "\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _insert_rich(self, text, plain=False):
        """Model cevabındaki markdown'ı (**kalın**, ## başlık, ---) ham işaret olarak göstermek yerine
        renklerle gösterir."""
        if plain:
            self.chat.insert("end", text)
            return
        lines = text.split("\n")
        for i, line in enumerate(lines):
            st = line.strip()
            if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", st):
                line = ""
            elif re.match(r"^#{1,6}\s+", st):
                self.chat.insert("end", re.sub(r"^#{1,6}\s+", "", st).replace("**", ""), "head")
                line = None
            if line is not None:
                line = re.sub(r"^(\s*)[*\-]\s+", r"\1• ", line)
                for j, part in enumerate(re.split(r"\*\*(.+?)\*\*", line)):
                    self.chat.insert("end", part.replace("`", ""), "b" if j % 2 else ())
            if i < len(lines) - 1:
                self.chat.insert("end", "\n")

    def _on_enter(self, event):
        self._send_text()
        return "break"

    def _on_shift_enter(self, event):
        self.entry._textbox.insert("insert", "\n")
        self._autosize_entry()
        return "break"

    def _select_all(self, event):
        tb = self.entry._textbox
        tb.tag_add("sel", "1.0", "end-1c")
        tb.mark_set("insert", "end-1c")
        return "break"

    def _set_chat_width(self, w):
        total = self.winfo_width() or 1200
        w = max(360, min(int(w), total - 520))           # sol menü + daire için yer kalsın
        self._chat_width = w
        self.grid_columnconfigure(3, weight=0, minsize=w)
        self.grid_columnconfigure(2, weight=1)
        try:
            self._right_panel.configure(width=w)
            self.confirm_label.configure(wraplength=max(300, w - 60))
        except Exception:
            pass

    def _drag_chat_sash(self, event):
        r = self._right_panel
        self._set_chat_width(r.winfo_rootx() + r.winfo_width() - event.x_root)

    def _chat_zoom(self, step):
        """Ctrl + / Ctrl - : sohbet ve yazı kutusu yazı boyutu (10-22), hatırlanır."""
        self._chat_font = max(10, min(22, self._chat_font + step))
        self.chat.configure(font=("Segoe UI", self._chat_font))
        self.entry.configure(font=("Segoe UI", self._chat_font))
        user_settings.set("chat_font", self._chat_font)
        self._flash_status(f"Yazı boyutu: {self._chat_font}")
        return "break"

    def _flash_status(self, text, ms=2500):
        """Dairenin altındaki durum satırında kısa süreli not (sohbete yazılmaz)."""
        try:
            self.status_label.configure(text=text)
            token = object()
            self._flash_token = token

            def back():
                if getattr(self, "_flash_token", None) is token and self._orb_state == "idle":
                    self.status_label.configure(text="Hazır")
            self.after(ms, back)
        except Exception:
            pass

    def _autosize_entry(self):
        lines = int(self.entry._textbox.index("end-1c").split(".")[0])
        if lines == getattr(self, "_entry_lines", None):      # satır sayısı aynıysa yeniden boyutlandırma (takılmayı önler)
            return
        self._entry_lines = lines
        self.entry.configure(height=min(max(46, 24 * lines + 14), 160))

    def _delete_word(self, event, forward=False):
        """Ctrl+Backspace: önceki kelimeyi, Ctrl+Delete: sonraki kelimeyi siler (Windows'taki alışkanlık)."""
        tb = event.widget
        try:
            if tb.tag_ranges("sel"):
                tb.delete("sel.first", "sel.last")
                return "break"
            if forward:
                end = tb.index("insert wordend")
                if tb.compare(end, "==", "insert"):
                    end = tb.index("insert +1c")
                tb.delete("insert", end)
            else:
                start = tb.index("insert -1c wordstart")
                while tb.compare(start, "<", "insert") and tb.get(start).isspace() and tb.compare(start, ">", "1.0"):
                    start = tb.index(f"{start} -1c wordstart")      # kelimeden önceki boşlukları da al
                tb.delete(start, "insert")
        except Exception:
            pass
        return "break"

    def _send_text(self):
        text = self.entry.get("1.0", "end").strip()
        if not text and not self._attachments:
            return
        self.entry.delete("1.0", "end")
        self._autosize_entry()
        self._append_chat("user", text or "(ekli dosyalar)")
        self._process_input(text)

    # ---------------- DOSYA EKLERİ ----------------
    def _on_paste(self, event=None):
        """Ctrl+V: panoda görsel varsa (ör. Win+Shift+S ekran alıntısı) onu ek olarak ekler;
        Gezgin'den kopyalanmış dosyalar varsa onları ekler; düz metinse normal yapıştırır."""
        try:
            from PIL import ImageGrab, Image
            clip = ImageGrab.grabclipboard()
        except Exception as e:
            print(f"[PANO] okunamadı: {e}")
            return None
        if isinstance(clip, Image.Image):
            folder = os.path.join("data", "ekler")
            os.makedirs(folder, exist_ok=True)
            path = os.path.abspath(os.path.join(folder, f"pano_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"))
            try:
                clip.convert("RGB").save(path)
            except Exception as e:
                self._append_chat("sys", f"⚠️ Panodaki görsel kaydedilemedi: {e}")
                return "break"
            self._add_attachment(path)
            self.status_label.configure(text="📋 Görsel eklendi, sorunu yazıp gönder")
            return "break"
        if isinstance(clip, list):
            files = [p for p in clip if isinstance(p, str) and os.path.isfile(p)]
            if files:
                for p in files:
                    self._add_attachment(p)
                return "break"
        return None          # metin: normal yapıştırma

    def _cleanup_pasted(self, days=7):
        """data/ekler altındaki eski yapıştırılmış görselleri siler."""
        folder = os.path.join("data", "ekler")
        if not os.path.isdir(folder):
            return
        limit = time.time() - days * 86400
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            try:
                if name.startswith("pano_") and os.path.getmtime(p) < limit:
                    os.remove(p)
            except Exception:
                pass

    def _pick_files(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(parent=self, title="FENIX'e dosya ekle", filetypes=att.FILETYPES)
        for p in paths:
            self._add_attachment(p)

    def _on_drop(self, event):
        for p in self.tk.splitlist(event.data):
            self._add_attachment(p)

    def _add_attachment(self, path):
        if len(self._attachments) >= 5:
            self._append_chat("sys", "En fazla 5 dosya eklenebilir.")
            return
        if any(os.path.normcase(a["path"]) == os.path.normcase(path) for a in self._attachments):
            return
        name = os.path.basename(path)
        self.status_label.configure(text=f"Okunuyor: {name}")
        # Dosyalar tek bir arka plan işçisinde SIRAYLA okunur (aynı anda ağır kütüphane
        # yüklemeleri çakışmasın, sıra korunsun)
        if not hasattr(self, "_attach_q"):
            self._attach_q = queue.Queue()
            threading.Thread(target=self._attach_worker, daemon=True).start()
        self._attach_q.put(path)

    def _attach_worker(self):
        while True:
            path = self._attach_q.get()
            name = os.path.basename(path)
            try:
                item = att.load(path)
                self.ui_queue.put(("attach_ok", item))
            except att.AttachmentError as e:
                self.ui_queue.put(("attach_err", (name, str(e))))
            except BaseException as e:
                self._record_error("dosya ekleme", f"{name}: {type(e).__name__}: {e}")
                self.ui_queue.put(("attach_err", (name, "Dosya okunamadı (ayrıntı Geçmiş'te).")))

    def _remove_attachment(self, idx):
        if 0 <= idx < len(self._attachments):
            self._attachments.pop(idx)
        self._render_chips()

    def _render_chips(self):
        for w in self.chips.winfo_children():
            w.destroy()
        if not self._attachments:
            self.chips.grid_forget()
            return
        self.chips.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        for i, a in enumerate(self._attachments):
            ctk.CTkButton(self.chips, text=f"{att.label(a)}   ✕", height=26, fg_color=PANEL2, hover_color="#7f1d1d",
                          text_color=TEXT, font=("Segoe UI", 11),
                          command=lambda i=i: self._remove_attachment(i)).pack(side="left", padx=(0, 6))

    def _take_attachments(self):
        atts, self._attachments = self._attachments, []
        self._render_chips()
        return atts

    def _remember(self, role, text, session_id=None):
        """Hafızaya yazar; kayıt hatası (ör. embedding kotası) cevabı asla engellemesin."""
        if session_id is None:
            if self.memory.incognito:
                self.memory.add_message(role, text)      # sadece bellekte (gizli sohbet bağlamı)
            return                       # sohbete bağlı olmayan sistem işleri (ör. gün özeti) konuşmaya yazılmaz
        try:
            self.memory.add_message(role, text, self.mode_key, session_id=session_id)
        except Exception as e:
            print(f"[HAFIZA UYARI] {role} mesajı kaydedilemedi: {e}")

    def _run_task(self, fn, user_text=None, session_id=None):
        """
        Bir görevi worker thread'de çalıştırır. Başarılı da olsa hata da verse
        sonunda MUTLAKA 'finish' sinyali gönderir; böylece pipeline takılı kalmaz.
        """
        self._cancel_event.clear()
        self._on_plan(["İşleniyor"])      # her görev paneli sıfırlar; ajan kendi adım planını sonra gönderir
        self.ui_queue.put(("orb", "thinking"))
        self.ui_queue.put(("status", "Düşünüyorum..."))

        def worker():
            ok = True
            speak_text = None
            t0 = time.time()
            try:
                if user_text:
                    self._remember("user", user_text, session_id)   # ağ çağrısı içerir: worker'da
                answer = fn()
            except GorevIptal:
                ok = False
                answer = "Görevi durdurdum."
            except Exception as e:
                ok = False
                self._record_error("görev", f"{type(e).__name__}: {e}")
                answer = "Bir hata ile karşılaştım. Ayrıntıyı Geçmiş'teki notlara kaydettim."
            if isinstance(answer, dict):           # derin araştırma: özet + ayrı rapor
                speak_text = answer.get("speak")
                if answer.get("report"):
                    self._cleanup_reports()      # sınırlar aşıldıysa eskileri sıkıştır/sil (sabitlenenler hariç)
                    self.ui_queue.put(("report", answer.get("report_path")))
                answer = answer.get("text", "")
            if ok:
                self._remember("assistant", answer, session_id)
            # cevap, görev başladığında açık olan sohbete aittir (bu arada başka sohbete geçilmiş olabilir)
            self.ui_queue.put(("answer", (session_id, answer, time.time() - t0)))
            if ok and session_id is not None:
                self._auto_title(session_id)
            self.ui_queue.put(("finish", ok))
            self.ui_queue.put(("orb", "idle"))
            self.ui_queue.put(("status", "Hazır" if ok else "Hata oluştu"))
            self.ui_queue.put(("history_refresh", None))
            if self.tts_enabled and ok:
                self._speak_async(speak_text or answer)

        threading.Thread(target=worker, daemon=True).start()

    def _process_input(self, text):
        stop_speaking()      # yeni komut geldi: eski cevabı okumayı bırak
        # Mod önerisine "evet" dendiyse: önerilen moda geç, asıl isteği orada yeniden çalıştır (v1.2.1)
        try:
            gecis = self.agent.mod_gecisi(text) if not self._attachments else None
        except Exception:
            gecis = None
        if gecis and gecis["mod"] in self.cfg.get("modes", {}):
            self.mode_var.set(gecis["mod"])
            self._on_mode_change()
            etiket = i18n.tr(self.cfg["modes"][gecis["mod"]].get("label", gecis["mod"]))
            self._append_chat("sys", f"{etiket} moduna geçtim: {gecis['sebep']}. İsteğini bu modda yeniden "
                                     "çalıştırıyorum.")
            text = gecis["metin"]
        atts = self._take_attachments()          # bekleyen ekler bu komutla gider (yazılı ya da sesli)
        names = ", ".join(a["name"] for a in atts)
        if atts:
            self._append_chat("sys", "📎 " + "  •  ".join(att.label(a) for a in atts))
        self._pipe["task"] = text + (f"  [📎 {names}]" if atts else "")
        mode_key = self.mode_key
        mode_cfg = self.cfg["modes"][mode_key]
        memo = text + (f"\n[Ekli dosyalar: {names}]" if atts else "")
        sid = self._ensure_session()
        self._run_task(lambda: (OGR.handle_and_learn(self, text, mode_key, mode_cfg, atts) if OGR else
                                self.agent.handle(text, mode_key, mode_cfg, attachments=atts or None)),
                       user_text=memo, session_id=sid)

    def run_day_summary(self, day, session_id=None):
        """Geçmiş penceresindeki 'Günü özetle' düğmesi (session_id verilirse o sohbetin o günü)."""
        mode_key = self.mode_key
        mode_cfg = self.cfg["modes"][mode_key]
        sess = self.memory.get_session(session_id) if session_id is not None else None
        title = sess["title"] if sess else None
        what = f"“{title}” sohbetinin {day} günü" if title else f"{day} günü"
        self._append_chat("sys", f"{what} özetleniyor...")
        self._pipe["task"] = f"{what} özeti"
        self._run_task(lambda: self.agent.summarize_day(day, mode_key, mode_cfg, session_id=session_id,
                                                        session_title=title))

    def _record_error(self, where, detail):
        """Hatayı sesli okumadan Geçmiş'e not düşer (her thread'den çağrılabilir)."""
        try:
            self.memory.log_error(where, detail)
        except Exception as e:
            print(f"[HATA KAYDI YAZILAMADI] {e}")
        self.ui_queue.put(("history_refresh", None))

    def _speak_async(self, text):
        """Cevabı sesli okur; kuyruğa ekler, beklemez."""
        overrides = self.cfg.get("pronunciation_overrides") or {}
        for a, b in overrides.items():
            text = text.replace(a, b)
        speak(text, self.cfg["audio"].get("tts_voice", "tr-TR-AhmetNeural"))

    def _gorev_suruyor(self):
        try:
            return bool(self._pipe.get("active")) and not self._cancel_event.is_set()
        except Exception:
            return False

    def _stop_speech(self):
        """Üstteki 'Durdur': konuşmayı keser; bir görev sürüyorsa onu da durdurur (07.11: iki düğme karışıyordu)."""
        stop_speaking()
        if self._gorev_suruyor():
            self._cancel_task()
        self._refresh_voice_btn()

    def _toggle_tts_button(self):
        self.tts_enabled = not self.tts_enabled
        if not self.tts_enabled:
            stop_speaking()
        if self.tts_enabled:
            self.tts_switch.select()
        else:
            self.tts_switch.deselect()
        user_settings.set("tts_enabled", self.tts_enabled)
        self._refresh_voice_btn()

    def _refresh_voice_btn(self):
        self.voice_btn.configure(text="🔊 Okuma: AÇIK" if self.tts_enabled else "🔇 Okuma: KAPALI",
                                 fg_color=self._accent() if self.tts_enabled else PANEL2,
                                 hover_color=self._accent_hover())
        speaking = is_speaking() or self._gorev_suruyor()
        self.stop_btn.configure(state="normal" if speaking else "disabled",
                                fg_color="#7f1d1d" if speaking else PANEL2)

    def _on_action_notify(self, text):
        """functions.py bir işlem yaptığında: pipeline günlüğüne yaz + Geçmiş'e olay olarak kaydet."""
        self.ui_queue.put(("pipeline_note", text))
        try:
            self.memory.log_event("action", text)
        except Exception as e:
            print(f"[OLAY KAYIT HATASI] {e}")

    # ---------------- MİKROFON (uygulama içi) ----------------
    def _transcribe(self, wav):
        """Kaydı yazıya çevirir; olmazsa sebebini durum satırına ve chat'e yazar."""
        a = self.cfg["audio"]
        text, why = stt.transcribe(
            wav, groq_key=(self.cfg["api_keys"].get("groq") or "").strip() if a.get("stt", "groq") == "groq" else "",
            model=a.get("stt_model", "whisper-large-v3-turbo"), device_name=self.recorder.device_name,
            on_error=self._record_error)
        if not text:
            self.ui_queue.put(("status", "Ses anlaşılamadı"))
            self.ui_queue.put(("chat", ("sys", f"🎤 {why}")))
            self.ui_queue.put(("orb", "idle"))
            return None
        return text

    def _toggle_mic(self):
        if not self._mic_recording:
            self._mic_recording = True
            self.mic_btn.configure(text="⏹  Bitir & Gönder", fg_color=CYAN)
            try:
                self.recorder.record_until_released_async()
            except Exception as e:
                self._mic_recording = False
                self.mic_btn.configure(text="🎤  Bas-Konuş", fg_color=PANEL)
                self._record_error("mikrofon", str(e))
                self._append_chat("sys", f"🎤 {e}" if isinstance(e, MicError) else "🎤 Mikrofon açılamadı (ayrıntı Geçmiş'te).")
                self.status_label.configure(text="Mikrofon açılamadı")
                return
            self.ui_queue.put(("orb", "listening"))
            self.ui_queue.put(("status", f"Dinliyorum…  ({self.recorder.device_name})"))
        else:
            self._mic_recording = False
            self.mic_btn.configure(text="🎤  Bas-Konuş", fg_color=PANEL)
            self.ui_queue.put(("orb", "thinking"))
            self.ui_queue.put(("status", "Çözümleniyor..."))

            def worker():
                wav = self.recorder.stop_async()
                text = self._transcribe(wav)
                if not text:
                    return
                self.ui_queue.put(("chat", ("user", text)))
                self.ui_queue.put(("process", text))

            threading.Thread(target=worker, daemon=True).start()

    # ---------------- ONAY KAPISI ----------------
    def _request_confirmation(self, title, message, detail=""):
        """Worker thread'den çağrılır, arayüzdeki onay kutusunu gösterip sonucu bekler."""
        self._confirm_event.clear()
        self._confirm_result["value"] = False
        self.ui_queue.put(("waiting", None))
        self.ui_queue.put(("confirm_show", (title, message, detail)))
        answered = self._confirm_event.wait(timeout=120)   # 2 dk içinde karar yoksa reddet
        if not answered:
            self.ui_queue.put(("chat", ("sys", "Onay zaman aşımına uğradı, işlem yapılmadı.")))
            self.ui_queue.put(("hide_confirm", None))
            return False
        return self._confirm_result["value"]

    def _show_confirm_box(self, title, message, detail):
        message = str(message or "")
        if len(message) > 400:
            message = message[:400] + "…"
        self.confirm_label.configure(text=f"⚠️ {title}\n{message}")
        box = self.confirm_detail
        box.configure(state="normal")
        box.delete("1.0", "end")
        if detail:
            detail = str(detail)
            lines = detail.count("\n") + 1 + len(detail) // 70
            box.insert("1.0", detail)
            box.configure(height=max(44, min(150, lines * 17)))
            box.pack(fill="x", padx=10, pady=(0, 10))
        else:
            box.pack_forget()
        box.configure(state="disabled")
        self.confirm_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        # Pencere arkada/simge durumundaysa öne getir ki onay kutusu kaçmasın
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(400, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _hide_confirm_box(self):
        self.confirm_frame.grid_forget()

    def _resolve_confirm(self, value):
        self._confirm_result["value"] = value
        self._hide_confirm_box()
        self._confirm_event.set()
        p = self._pipe
        if p["active"] and 0 <= p["idx"] < len(p["steps"]):
            self.pipe_stage.configure(text=p["steps"][p["idx"]], text_color=self._accent())
        self.pipe_log.insert("end", f"• onay: {'verildi' if value else 'reddedildi'}\n")

    # ---------------- AYRI PENCERELER ----------------
    def _open_window(self, key, factory):
        """Aynı pencere zaten açıksa yenisini açmak yerine öne getirir."""
        win = self._windows.get(key)
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            win.focus()
            if hasattr(win, "refresh"):
                try:
                    win.refresh()          # tekrar açılınca güncel bilgiyi göstersin
                except Exception:
                    pass
            return win
        win = factory()
        self._windows[key] = win
        # Windows'ta yeni Toplevel bazen ana pencerenin arkasında kalır
        win.lift()
        win.attributes("-topmost", True)
        win.after(300, lambda: win.winfo_exists() and win.attributes("-topmost", False))
        return win

    def _stats_text(self):
        s = self.stats
        load = s.system_load()
        lines = [
            "SİSTEM (canlı)",
            f"  CPU           : {load.get('cpu')}",
            f"  FENIX RAM    : {load.get('ram_mb')} MB",
            f"  Sistem RAM    : {load.get('ram_total', '?')}",
            "",
            "BU OTURUM",
            f"  Süre          : {s.session_minutes()} dk",
        ]
        brk = s.category_breakdown()
        if brk:
            for cat, sec in brk.items():
                lines.append(f"  {cat:<13}: {round(sec / 60, 1)} dk")
        else:
            lines.append("  (veri toplanıyor... her 15 sn'de bir örnekleniyor)")
        today = self.memory.get_activity_summary()
        lines += ["", "BUGÜN (tüm oturumlar)"]
        if today:
            for cat, mins in today.items():
                lines.append(f"  {cat:<13}: {mins} dk")
        else:
            lines.append("  (henüz kayıt yok)")
        lines += ["", "Bu pencere her 2 saniyede bir kendini yeniler."]
        return "\n".join(lines)

    def _skills_text(self):
        lines = ["TEMEL YETENEKLER",
                 "  • Sesli ve yazılı sohbet (Bas-Konuş / yazı)",
                 "  • Ekranı görme: 'ekrandaki hata ne' gibi isteklerde tek kare yakalar",
                 "  • Kalıcı hafıza: önceki konuşmaları hatırlar",
                 "  • Not alma: 'not al: ...' ile Geçmiş'e not düşer",
                 "  • Gün özeti: 'bugün ne yaptık özetle'",
                 "  • Web sitesi analizi (Normal/Devil): 'github.com sitesini analiz et'",
                 "",
                 "SİSTEM EYLEMLERİ (Normal ve Devil modda)"]
        for sch in fx.FUNCTION_SCHEMAS:
            desc = i18n.tool_desc(sch["name"], sch["description"].split(".")[0])
            lines.append(f"  • {sch['name']}: {desc}")
        lines += ["",
                  "ONAY KURALI",
                  "  Silme, format, kapatma, indirme gibi riskli komutlar HER modda",
                  "  onay kutusu ile sorulur.",
                  "",
                  "MODLARA GÖRE YETKİ"]
        for key in MODE_KEYS:
            m = self.cfg["modes"][key]
            lines.append(f"  • {m['label']}: sistem eylemleri {'AÇIK' if m.get('allow_actions') else 'KAPALI'}")
        n_yol, n_proje = len(YOLH.yollar()), len(YOLH.projeler())
        lines += ["", "YOL HAFIZASI", f"  • {'Açık' if YOLH.acik() else 'Kapalı'} · öğrenilmiş yol: {n_yol} · "
                                      f"bilinen proje klasörü: {n_proje}"]
        lines += ["", "EKLENTİLER (MCP)"] + ["  " + x for x in MCPX.durum_metni().splitlines()]
        lines += ["", "KISAYOL KOMUTLARIN (tek cümleyle birden çok iş)"]
        ms = macro_store.load()
        if ms:
            for name, steps in ms.items():
                lines.append(f"  • '{name}': " + " → ".join(steps))
        else:
            lines.append("  (henüz yok) Örnek: \"çalışma modu dediğimde VS Code'u, Spotify'ı ve proje klasörünü aç\"")
        st = cmem.stats()
        lines += ["",
                  "KOMUT HAFIZASI (v5.9.0)",
                  f"  • {st['kayit']} kalıp öğrenildi; yapay zekâya gitmeden {st['yerel']} kez çalıştırıldı",
                  "  • Normal/Devil modda tek araçlı kısa komutlar ('ses aç', 'spotify'ı aç') ilk seferde yapay zekâyla",
                  "    çözülür, sonraki seferler yerelde çalışır. 'Öğrendiklerim' penceresinden silebilirsin.",
                  "  • 'kendini eğit' → araçlar için söylenişler üretir; 'bilgisayarı tara' → uygulama envanteri;",
                  "    'ses aç komutunu unut' / 'yanlış anladın' → kalıbı siler",
                  "",
                  "NÖBET MODU (v5.10.0)",
                  "  • Pencereyi kapatırken 'Nöbette kal' seç: küçük bir izleme işlemi sağ alttaki simgede sürer",
                  "    (yaklaşık 40-60 MB). Simgeden sesli uyarı düzeyini ayarlar, 1 saat duraklatır ya da bitirirsin.",
                  "  • İzledikleri: İndirilenler'e inen dosyalar (çift uzantı, imzasız program, arşivde program,",
                  "    Defender sonucu), panoya kopyalanan linkler (şüpheliyse uyarır), cüzdan adresi değişimi,",
                  "    riskli yoldan başlayan programlar, uzun süre işlemciyi dolduran program, pil, açılış programları.",
                  "  • Belge/resim içeriği okunmaz, pano metni ve dosyalar saklanmaz ya da gönderilmez; ekran ve",
                  "    mikrofon izlenmez. Kill-switch (Ctrl+Alt+Q, sol üst köşe) nöbeti de tamamen kapatır.",
                  "",
                  "YAN SOHBET (v5.10.1)",
                  "  • Nöbetteyken simgeye tıkla ya da Ctrl+Alt+J: küçük, yazılı bir sohbet penceresi açılır (kapatınca RAM'i bırakır).",
                  "  • Güvenli / Normal mod seçilebilir; komut hafızası ve araçlar aynıdır. Derin araştırma (Devil), ekran görme ve",
                  "    dosya ekleme için ana pencere gerekir. Sohbet bugünün 'Yan sohbet' kaydına yazılır, Geçmiş'te görünür.",
                  "  • 'Bunu kapat' (FENIX dışında en öndeki pencereyi nazikçe kapatır), 'ne çalışıyor', 'bilgisayar yavaşladı'",
                  "    ana pencerede de çalışır. Pencere başlıkları okunmaz, yalnızca program adı söylenir.",
                  "",
                  "GÜVENLİK (v5.7.x)",
                  "  Tespit (her modda, sadece okur):",
                  "  • 'bilgisayarımın güvenliği nasıl': Defender, güvenlik duvarı, SmartScreen, UAC, güncellemeler",
                  "  • 'şüpheli bir şey çalışıyor mu': sistem taklidi / Temp'ten çalışan / imzasız süreçler",
                  "  • 'başlangıçta değişiklik var mı': açılışta başlayan programlar (arka planda da izlenir;",
                  "    FENIX penceresi arkadayken değişiklik olursa Windows bildirimi de gelir, v5.7.3)",
                  "  Müdahale (Normal/Devil, her biri onay kutusu ister):",
                  "  • süreç sonlandırma • başlangıçtan kaldırma (yedekli) / geri yükleme",
                  "  • Defender ve güvenlik duvarını açma (ayrıca Windows UAC onayı)",
                  "",
                  "BEKLEYEN HATIRLATMALAR"]
        pend = self.reminders.pending()
        lines += [f"  • [{r['id']}] {human_when(r['due'])} — {r['text']}" for r in pend] or ["  (yok)"]
        pr = audio_io.get_prosody()
        lines += ["", f"SES AYARI  hız {pr['rate']} • ton {pr['pitch']} • yükseklik {pr['volume']}",
                  "  'daha yavaş konuş', 'sesini incelt', 'ses ayarını sıfırla' diyerek değiştirebilirsin."]
        lines += ["", "LİSANS",
                  "  • FENIX © 2026 Mustafa Koç · GNU GPL v3 (GPL-3.0-only) ve ek şartlar (LICENSE, NOTICE.md)",
                  "  • Kullanabilir, değiştirebilir, paylaşabilirsin: aynı lisansla, atfı koruyarak, başka bir adla.",
                  "  • HİÇBİR GARANTİ YOKTUR. Resmi kaynak: github.com/fever11/fenix"]
        return "\n".join(lines)

    def _settings_text(self):
        c = self.cfg
        lines = ["API ANAHTARLARI (maskeli)",
                 f"  Gemini : {mask_key(c['api_keys'].get('gemini'))}",
                 f"  Groq   : {mask_key(c['api_keys'].get('groq'))}",
                 f"  NVIDIA : {mask_key(c['api_keys'].get('nvidia'))}",
                 f"  Tavily : {mask_key(c['api_keys'].get('tavily'))}",
                 "  Groq → NVIDIA → Gemini",
                 "",
                 f"MODLAR  (varsayılan: {c.get('default_mode')})"]
        for key in MODE_KEYS:
            m = c["modes"][key]
            lines += [f"  {m['label']}",
                      f"    sağlayıcı     : {m.get('provider')}",
                      f"    groq modeli   : {m.get('groq_model')}",
                      f"    gemini modeli : {m.get('gemini_model')}",
                      f"    sistem eylemi : {'açık' if m.get('allow_actions') else 'kapalı'}"]
        a = c["audio"]
        k = c["killswitch"]
        lines += ["",
                  "SES",
                  f"  Ses            : {a.get('tts_voice')}",
                  f"  Bas-konuş tuşu : {a.get('ptt_key')}",
                  f"  Ses tanıma     : {'Groq Whisper (' + a.get('stt_model', 'whisper-large-v3-turbo') + ') + Google yedek' if a.get('stt', 'groq') == 'groq' and (c['api_keys'].get('groq') or '').strip() else 'Google'}",
                  f"  Mikrofon ayarı : {a.get('input_device') or 'Windows varsayılanı'}",
                  f"  Son kullanılan : {self.recorder.device_name}",
                  "  Bulunan mikrofonlar (config.yaml -> audio.input_device'a numara ya da ad parçası yaz):"]
        try:
            for idx, name, is_default in list_input_devices():
                lines.append(f"    [{idx}] {name}{'   ← varsayılan' if is_default else ''}")
        except Exception as e:
            lines.append(f"    (listelenemedi: {e})")
        lines += [
                  "",
                  "NÖBET MODU",
                  f"  Durum          : {'kullanılabilir' if nobet.available() else 'kullanılamıyor (Windows + pip install pystray gerekir)'}",
                  f"  Kapatırken     : {self._nobet_cfg.get('kapanis_tercihi')}  (sor / nobet / kapat)",
                  f"  Yan sohbet     : {'açık' if self._nobet_cfg.get('yan_sohbet') else 'kapalı'}, kısayol {self._nobet_cfg.get('yan_sohbet_kisayol')}, mod {self._nobet_cfg.get('yan_sohbet_mod')}",
                  f"  Sesli uyarı    : {self._nobet_cfg.get('uyari_sesi')}  (onemli / hepsi / sessiz); sessiz saat: {self._nobet_cfg.get('sessiz_saat') or 'yok'}",
                  "",
                  "ACİL KAPATMA",
                  f"  Kısayol        : {k.get('hotkey')}",
                  f"  Fare köşesi    : {'açık' if k.get('corner_trigger') else 'kapalı'}",
                  "",
                  "HAFIZA DOSYALARI",
                  f"  SQLite  : {c['memory'].get('db_path')}",
                  f"  Chroma  : {c['memory'].get('chroma_path')}",
                  "",
                  "Ayarları değiştirmek için config.yaml dosyasını düzenleyip",
                  "kaydet (Ctrl+S) ve FENIX'i yeniden başlat."]
        return "\n".join(lines)

    def _show_lab(self):
        self._open_window("lab", lambda: OGR.lab_window(self, ReadOnlyWindow, globals()))

    def _show_learned(self):
        self._open_window("learned", lambda: LearnedWindow(self))

    def _show_stats(self):
        self._open_window("stats", lambda: ReadOnlyWindow(self, "İstatistikler", self._stats_text,
                                                          interval_ms=2000, size="460x520"))

    def _show_skills(self):
        self._open_window("skills", lambda: ReadOnlyWindow(self, "Yetenekler", self._skills_text,
                                                           size="560x600"))

    def _notify_answer(self, text):
        """Kullanıcı başka bir penceredeyken (tarayıcı vb.) cevap gelirse sağ altta Windows bildirimi gösterir."""
        try:
            if not user_settings.get("cevap_bildirimi", True) or self._window_in_front():
                return
            plain = re.sub(r"[*_`#>]+", "", str(text or "")).strip()
            plain = " ".join(plain.split())
            if plain:
                notifier.show_toast_async(i18n.tr("FENIX cevap verdi"), plain[:180] + ("…" if len(plain) > 180 else ""))
        except Exception:
            pass

    def _show_plugins(self):
        return self._open_window("plugins", lambda: PluginsWindow(self))

    def _show_settings(self):
        self._open_window("settings", lambda: SettingsWindow(self, self._settings_text))

    def _show_reports(self, select_path=None):
        win = self._windows.get("reports")
        if win is not None and win.winfo_exists():
            win.refresh_list()
            if select_path:
                win.select(select_path)
            win.deiconify()
            win.lift()
            return win
        return self._open_window("reports", lambda: ReportsWindow(self, select_path))

    def _setup_drag_drop(self):
        if not TkinterDnD:
            return
        try:
            self.TkdndVersion = TkinterDnD._require(self)
            targets = [self, self.chat._textbox, self.entry._textbox, self.canvas]
            for w in targets:
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._on_drop)
                except Exception:
                    # alt widget DnD sarmalayıcısı değilse tk komutlarıyla kaydet
                    TkinterDnD.DnDWrapper.drop_target_register(w, DND_FILES)
                    TkinterDnD.DnDWrapper.dnd_bind(w, "<<Drop>>", self._on_drop)
        except Exception as e:
            print(f"[SÜRÜKLE-BIRAK] kullanılamıyor: {e}")

    def _cleanup_reports(self):
        try:
            res = self.reports.cleanup()
            if res["compressed"] or res["deleted"]:
                print(f"[RAPOR] temizlik: {res['compressed']} sıkıştırıldı, {res['deleted']} silindi")
        except Exception as e:
            print(f"[RAPOR] temizlik hatası: {e}")

    def _show_chat_history(self):
        """Başlığın yanındaki 📜: açık sohbetin geçmişi."""
        win = self._show_history()
        if win is not None:
            win.set_scope("session" if self.session_id is not None else "all")

    def _show_history(self):
        win = self._open_window("history", lambda: HistoryWindow(self))
        try:
            win.refresh()          # zaten açıksa güncel sohbetlerle yenilensin
        except Exception:
            pass
        return win

    def _toggle_tts(self):
        self.tts_enabled = bool(self.tts_switch.get())
        if not self.tts_enabled:
            stop_speaking()
        user_settings.set("tts_enabled", self.tts_enabled)
        self._refresh_voice_btn()

    # ---------------- MOD ----------------
    def _on_mode_change(self):
        self.mode_key = self.mode_var.get()
        if hasattr(self, "mode_seg") and self.mode_seg.get() != self._mode_labels.get(self.mode_key):
            self.mode_seg.set(self._mode_labels.get(self.mode_key))
        self.llm.reset_mode_session(ortak_koru=True)      # mod değişince konuşma unutulmaz (04.11)
        self._update_mode_desc()
        self._apply_mode_theme()
        self._flash_status("Mod: " + i18n.tr(self.cfg['modes'][self.mode_key]['label']))   # sohbete yazılmaz
        if OGR:
            OGR.sync(self)

    def _update_mode_desc(self):
        desc = {
            "safe": "Sadece okuma ve sohbet. Sisteme dokunmaz.",
            "normal": "Gündelik asistan. Güvenli işlemleri yapar, riskli olanları sorar.",
            "devil": "Derin analiz & ajan. Web analizi, çok adımlı görevler. Kritik işlemlerde yine onay.",
            **(OGR.MODE_DESC if OGR else {}),
        }.get(self.mode_key, "")
        self.mode_desc.configure(text=desc)

    # ---------------- ARKA PLAN ----------------
    def _start_background(self):
        # Global PTT dinleyici (uygulama odakta olmasa bile)
        def ptt_loop():
            while True:
                try:
                    wav = self.recorder.record(
                        on_start=lambda: self.ui_queue.put(("orb", "listening")),
                        on_stop=lambda: self.ui_queue.put(("orb", "thinking")),
                    )
                    self._ptt_listening = False
                    text = self._transcribe(wav)
                    if text:
                        self.ui_queue.put(("chat", ("user", text)))
                        self.ui_queue.put(("process", text))
                except MicError as e:
                    self._record_error("mikrofon (F9)", str(e))
                    self.ui_queue.put(("chat", ("sys", f"🎤 {e}")))
                    self.ui_queue.put(("orb", "idle"))
                    time.sleep(1)
                except Exception as e:
                    print(f"[PTT HATASI] {e}")
                    time.sleep(1)

        threading.Thread(target=ptt_loop, daemon=True).start()

        # Sistem yükü göstergesi
        def load_loop():
            while True:
                load = self.stats.system_load()
                self.ui_queue.put(("load", f"CPU {load.get('cpu')} • {load.get('ram_mb')}MB"))
                time.sleep(3)

        threading.Thread(target=load_loop, daemon=True).start()

    # ---------------- NÖBET MODU (v5.10.0) ----------------
    def _start_gozcu(self):
        """Pencere açıkken de indirilenler / pano / süreç bekçisi çalışır (başlangıç bekçisini kendi döngüsü yapar)."""
        if os.name != "nt" or not self._nobet_cfg.get("uygulama_acikken", True):
            return
        try:
            self._gozcu = nobet.Gozcu(self._nobet_cfg, lambda ev: self.ui_queue.put(("gozcu_alert", ev)),
                                      is_app=True).start()
        except Exception as e:
            print(f"[NÖBET] gözcü başlatılamadı: {e}")

    def _nobet_choice(self):
        """Kapatırken: 'nobet' | 'kapat' | None (vazgeç). Nöbet kullanılamıyorsa doğrudan 'kapat'."""
        cfg = self._nobet_cfg
        if not cfg.get("etkin", True) or not nobet.available():
            return "kapat"
        pref = cfg.get("kapanis_tercihi", "sor")
        if pref == "nobet":
            return "nobet"
        if pref == "kapat":
            return "kapat"
        dlg = NobetDialog(self)
        self.wait_window(dlg)
        if dlg.result and dlg.remember:
            cfg["kapanis_tercihi"] = dlg.result
            nobet.save_user_settings(kapanis_tercihi=dlg.result)
        return dlg.result

    def _finish_close(self):
        if OGR:
            OGR.shutdown(self)
        try:
            MCPX.durdur()
        except Exception:
            pass
        self.stats.stop()
        self.destroy()
        os._exit(0)

    def _on_close(self):
        choice = self._nobet_choice()
        if choice is None:
            return
        if choice == "nobet":
            if not nobet.start_background():
                self._append_chat("sys", "Nöbet modu başlatılamadı, FENIX açık kalıyor. Ayrıntı için data\\hatalar.log'a bak "
                                         "ya da 'pip install pystray' yaptığından emin ol.")
                return
        self._finish_close()

    def _go_nobet(self):
        """Menüden 'Nöbete geç': pencereyi kapatıp izlemeyi arka planda sürdürür."""
        if not nobet.available():
            self._append_chat("sys", "Nöbet modu için Windows ve 'pystray' paketi gerekli. Terminalde "
                                     "'pip install pystray' yazıp FENIX'i yeniden başlat.")
            return
        if nobet.start_background():
            self._finish_close()
        else:
            self._append_chat("sys", "Nöbet modu başlatılamadı. Ayrıntı için data\\hatalar.log'a bak.")


def _install_crash_logging():
    """Uygulama beklenmedik şekilde kapanırsa sebebi data/hatalar.log (ve donanım/yerel çökme için
    data/cokme.log) dosyasına yazılsın. pythonw ile konsolsuz çalışırken başka türlü görünmez."""
    import sys
    import traceback
    import faulthandler
    from modules.killswitch import log_exit
    os.makedirs("data", exist_ok=True)
    try:
        from modules.killswitch import trim_log
        crash_path = os.path.join("data", "cokme.log")
        if os.path.exists(crash_path):
            trim_log(crash_path)
        faulthandler.enable(open(crash_path, "a", encoding="utf-8"))
    except Exception:
        pass

    def _log(prefix, etype, value, tb):
        log_exit(f"ÇÖKME — {prefix}: {etype.__name__}: {value}\n" + "".join(traceback.format_tb(tb))[-2000:])

    sys.excepthook = lambda et, v, tb: _log("çökme", et, v, tb)
    threading.excepthook = lambda a: _log(f"iş parçacığı hatası ({a.thread.name if a.thread else '?'})",
                                          a.exc_type, a.exc_value, a.exc_traceback)


def choose_language_first_run(cfg_lang=""):
    """İlk açılışta dil seçtirir (data/ayarlar.json'a kaydedilir). / First-run language picker.
    Kurulum ya da config.yaml dili zaten belirlediyse sormaz."""
    from modules import user_settings
    if user_settings.get("language") or str(cfg_lang or "").lower() in i18n.LANGS:
        return
    picked = {"code": i18n.system_language()}
    win = ctk.CTk()
    win.title("FENIX")
    win.geometry("360x420")
    win.resizable(False, False)
    ctk.CTkLabel(win, text="F.E.N.I.X.", font=(FONT_HEAD, 26, "bold"), text_color="#f97316").pack(pady=(24, 4))
    ctk.CTkLabel(win, text="Dil seçin / Choose your language", font=("Segoe UI", 13)).pack(pady=(0, 14))

    def pick(code):
        picked["code"] = code
        win.destroy()
    for code, name in i18n.LANGS.items():
        ctk.CTkButton(win, text=name, width=220, height=36, fg_color="#c2410c", hover_color="#ea580c",
                      command=lambda c=code: pick(c)).pack(pady=4)
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    win.mainloop()
    i18n.save_language(picked["code"])


GEMINI_KEY_URL = "https://aistudio.google.com/apikey"
GROQ_KEY_URL = "https://console.groq.com/keys"
NVIDIA_KEY_URL = "https://build.nvidia.com/settings/api-keys"
TAVILY_KEY_URL = "https://app.tavily.com/home"


def _key_missing(cfg):
    k = ((cfg.get("api_keys") or {}).get("gemini") or "").strip()
    return not k or k.startswith("BURAYA")


def _put_key(text, name, value):
    """config.yaml metninde api_keys altındaki tek bir anahtarı yazar; açıklamalar ve diğer ayarlar korunur."""
    value = value.replace('"', "").strip()
    rx = re.compile(r'^(\s+)' + re.escape(name) + r':[ \t]*(".*?"|\'.*?\'|[^\n#]*)', re.M)
    if rx.search(text):
        return rx.sub(lambda m: f'{m.group(1)}{name}: "{value}"', text, count=1)
    return text.replace("api_keys:\n", f'api_keys:\n  {name}: "{value}"\n', 1)


def save_key(path, name, value):
    """Tek bir API anahtarını config.yaml'a kaydeder (ör. eklentiler penceresinden Notion anahtarı)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(_put_key(text, name, value))


def save_keys(path, gemini, groq="", nvidia="", tavily=""):
    """Anahtarları config.yaml'a yazar; dosyadaki açıklamalar ve diğer ayarlar korunur."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    put = _put_key
    text = put(text, "gemini", gemini)
    if groq.strip():
        text = put(text, "groq", groq)
    if nvidia.strip():
        text = put(text, "nvidia", nvidia)
    if tavily.strip():
        text = put(text, "tavily", tavily)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _test_gemini(key):
    """Anahtarı küçük bir istekle dener -> (True, '') ya da (False, sebep)."""
    try:
        from google import genai
        client = genai.Client(api_key=key)
        next(iter(client.models.list()), None)
        return True, ""
    except Exception as e:
        msg = str(e)
        return False, (msg[:160] + "…") if len(msg) > 160 else msg


def setup_keys_window(path="config.yaml"):
    """Anahtar yoksa açılan basit pencere: kullanıcı YAML düzenlemeden anahtarını yapıştırır.
    Simple first-run window so users never have to edit YAML. -> True (kaydedildi) / False (vazgeçildi)"""
    import webbrowser
    done = {"ok": False, "force": False}
    win = ctk.CTk()
    win.title("FENIX • Kurulum")
    win.geometry("520x660")
    win.resizable(False, False)
    try:
        win.iconbitmap("fenix.ico")
    except Exception:
        pass
    ctk.CTkLabel(win, text="🔑 API anahtarı", font=(FONT_HEAD, 20, "bold"), text_color="#f97316").pack(pady=(20, 6))
    ctk.CTkLabel(win, text="FENIX'in çalışması için ücretsiz bir Gemini anahtarı gerekir. Anahtar yalnızca bu bilgisayarda "
                           "(config.yaml) saklanır, kimseyle paylaşılmaz.",
                 wraplength=460, justify="left").pack(padx=24, pady=(0, 10))
    ctk.CTkButton(win, text="🌐 Ücretsiz Gemini anahtarı al", fg_color="#c2410c", hover_color="#ea580c",
                  command=lambda: webbrowser.open(GEMINI_KEY_URL)).pack(pady=(0, 12))
    ctk.CTkLabel(win, text="Gemini API anahtarı (zorunlu)", anchor="w").pack(fill="x", padx=24)
    e_gem = ctk.CTkEntry(win, placeholder_text="AIza...", show="•", width=470)
    e_gem.pack(padx=24, pady=(2, 10))
    ctk.CTkLabel(win, text="Groq API anahtarı (isteğe bağlı: daha hızlı sohbet ve ses tanıma)", anchor="w").pack(fill="x", padx=24)
    row = ctk.CTkFrame(win, fg_color="transparent")
    row.pack(fill="x", padx=24, pady=(2, 6))
    e_groq = ctk.CTkEntry(row, placeholder_text="gsk_...", show="•", width=330)
    e_groq.pack(side="left")
    ctk.CTkButton(row, text="Groq anahtarı al", width=130, fg_color="#374151",
                  command=lambda: webbrowser.open(GROQ_KEY_URL)).pack(side="right")
    ctk.CTkLabel(win, text="NVIDIA API anahtarı (isteğe bağlı: Groq dolunca yedek sohbet)", anchor="w").pack(fill="x", padx=24)
    row2 = ctk.CTkFrame(win, fg_color="transparent")
    row2.pack(fill="x", padx=24, pady=(2, 6))
    e_nv = ctk.CTkEntry(row2, placeholder_text="nvapi-...", show="•", width=330)
    e_nv.pack(side="left")
    ctk.CTkButton(row2, text="NVIDIA anahtarı al", width=130, fg_color="#374151",
                  command=lambda: webbrowser.open(NVIDIA_KEY_URL)).pack(side="right")
    ctk.CTkLabel(win, text="Tavily API anahtarı (isteğe bağlı: daha iyi web araması, aylık ücretsiz kota)", anchor="w").pack(fill="x", padx=24)
    row3 = ctk.CTkFrame(win, fg_color="transparent")
    row3.pack(fill="x", padx=24, pady=(2, 6))
    e_tav = ctk.CTkEntry(row3, placeholder_text="tvly-...", show="•", width=330)
    e_tav.pack(side="left")
    ctk.CTkButton(row3, text="Tavily anahtarı al", width=130, fg_color="#374151",
                  command=lambda: webbrowser.open(TAVILY_KEY_URL)).pack(side="right")
    status = ctk.CTkLabel(win, text="", wraplength=460, justify="left", text_color="#fbbf24")
    status.pack(padx=24, pady=(8, 4))
    btn = ctk.CTkButton(win, text="Kaydet ve başlat", height=38, fg_color="#059669", hover_color="#10b981")
    btn.pack(pady=(4, 6))
    ctk.CTkButton(win, text="Vazgeç", fg_color="transparent", border_width=1, command=win.destroy).pack()

    def finish(gem, groq):
        save_keys(path, gem, groq, e_nv.get().strip(), e_tav.get().strip())
        done["ok"] = True
        win.destroy()

    def on_save():
        gem, groq = e_gem.get().strip(), e_groq.get().strip()
        if len(gem) < 20:
            status.configure(text="Gemini anahtarını yapıştır (genellikle AIza ile başlar).")
            return
        if done["force"]:
            finish(gem, groq)
            return
        btn.configure(state="disabled")
        status.configure(text="Anahtar deneniyor...", text_color="#9ca3af")
        res = {}
        threading.Thread(target=lambda: res.setdefault("r", _test_gemini(gem)), daemon=True).start()

        def poll():
            if "r" not in res:
                win.after(200, poll)
                return
            btn.configure(state="normal")
            ok, why = res["r"]
            if ok:
                finish(gem, groq)
            else:
                done["force"] = True
                status.configure(text=i18n.tr(f"Anahtar denenemedi: {why}") + "\n" +
                                 i18n.tr("Anahtarın doğru olduğundan eminsen yine de kaydedebilirsin."),
                                 text_color="#f87171")
                btn.configure(text="Yine de kaydet")
        poll()
    btn.configure(command=on_save)
    win.bind("<Return>", lambda e: on_save())
    win.mainloop()
    return done["ok"]


def _single_instance():
    """Windows'ta FENIX zaten açıksa ikinci kopya açılmaz; açık olan pencere öne getirilir.
    (Açılış birkaç saniye sürünce simgeye tekrar tıklanıyor ve iki FENIX açılıyordu.) -> True: devam et"""
    if os.name != "nt":
        return True
    try:
        import ctypes
        k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
        _single_instance.handle = k32.CreateMutexW(None, False, "Local\\FENIX_MK_single_instance")
        if k32.GetLastError() != 183:          # ERROR_ALREADY_EXISTS değil: ilk kopya
            return True
        hwnd = u32.FindWindowW(None, "F.E.N.I.X.")
        if hwnd:
            u32.ShowWindow(hwnd, 9)            # SW_RESTORE
            u32.SetForegroundWindow(hwnd)
        return False
    except Exception:
        return True


def main():
    if not _single_instance():
        return
    _install_crash_logging()
    import tkinter.messagebox as mb
    from modules.config_check import ensure_config
    os.makedirs("data", exist_ok=True)
    state = ensure_config()                 # yoksa config.example.yaml'dan sessizce oluşturulur
    pre = {}
    if state != "yok":
        try:
            pre = load_config() or {}
        except Exception:
            pre = {}
    choose_language_first_run(pre.get("language"))
    i18n.init(None)
    i18n.install_tk_hooks()
    if state == "yok":
        mb.showerror("FENIX", "config.yaml bulunamadı.\nProje klasöründeki config.example.yaml dosyasını kopyalayıp adını "
                               "config.yaml yap, içine Gemini API anahtarını yapıştır. Detay: docs/ klasöründeki kurulum rehberi.")
        return
    cfg = load_config()
    if _key_missing(cfg):
        if not setup_keys_window():
            return
        cfg = load_config()
    i18n.init(cfg)
    ks = cfg["killswitch"]
    KillSwitch(ks["hotkey"], ks["corner_trigger"], ks["corner_size"], ks.get("corner_hold_seconds", 1.5)).start()
    app = FenixApp(cfg)

    def _tk_error(etype, value, tb):        # arayüz geri çağrılarındaki hatalar uygulamayı düşürmesin, kaydedilsin
        import traceback
        from modules.killswitch import log_exit
        log_exit(f"arayüz hatası: {etype.__name__}: {value}\n" + "".join(traceback.format_tb(tb))[-1500:])
        print(f"[ARAYÜZ HATASI] {etype.__name__}: {value}")
    app.report_callback_exception = _tk_error
    app.mainloop()


if __name__ == "__main__":
    main()
