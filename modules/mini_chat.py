# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Yan sohbet (v5.10.1)
--------------------
Nöbet modundayken (ana pencere kapalı) simgeden ya da Ctrl+Alt+J ile açılan küçük, YAZILI sohbet penceresi.
Ayrı ve kısa ömürlü bir işlemdir: pencereyi kapatınca bütün belleği geri verir.

  • Aynı ajan, aynı araçlar, aynı komut hafızası; sadece daha hafif: anlamsal arama (chromadb), Gemini ve ses
    paketleri yüklenmez (ses ancak "Sesli oku" açılırsa).
  • Modlar: Güvenli (işlem yapmaz, sadece cevap) ve Normal. Derin araştırma (Devil) için ana pencere gerekir.
  • Sohbetler bugünün "Yan sohbet" kaydına yazılır; ana pencerenin Geçmiş'inde de görünür.
  • "Bunu kapat" gibi komutlar, FENIX'in kendisi dışında en öndeki pencereyi hedef alır.
  • Ekran görme, dosya ekleme ve eski sohbetlerde anlamsal arama yoktur (ana pencerede var).
"""
import os
import re
import sys
import time
import queue
import datetime
import threading

from . import i18n

DATA_DIR = "data"
PID_PATH = os.path.join(DATA_DIR, "yan_sohbet.pid")
SHOW_PATH = os.path.join(DATA_DIR, "yan_sohbet.goster")

MODES = {"Güvenli": "safe", "Normal": "normal"}
MODE_LABELS = {v: k for k, v in MODES.items()}

# ana pencereyle aynı renkler
BG, PANEL, PANEL2 = "#0a0f1d", "#111827", "#0d1424"
EMERALD, CYAN, AMBER, TEXT, MUTED = "#10b981", "#06b6d4", "#f59e0b", "#e5e7eb", "#6b7280"


# ------------------------------------------------------------------ arka uç (arayüzden bağımsız, test edilebilir)
class Backend:
    """Bellek + dil modeli + ajan. Ağır paketler yüklenmeden kurulur (semantic=False, lazy_gemini=True)."""

    def __init__(self, cfg, confirm=None, on_stage=None, voice=False):
        from . import functions as fx
        from .memory import Memory
        from .llm_client import LLMClient
        from .agent import Agent
        from .reminders import ReminderStore
        self.cfg = cfg
        self.fx = fx
        self.voice = bool(voice)
        mem_cfg = cfg.get("memory") or {}
        keys = cfg.get("api_keys") or {}
        self.memory = Memory(mem_cfg.get("db_path", "data/fenix_memory.db"), mem_cfg.get("chroma_path"),
                             keys.get("gemini"), cross_chat=mem_cfg.get("cross_chat", True), semantic=False)
        bk = keys.get("gemini_yedek") or []
        try:
            from . import nvidia
            nvidia.configure(cfg)       # NVIDIA: sohbet yedeği + görme son yedeği
        except Exception:
            pass
        self.llm = LLMClient(keys.get("gemini", ""), keys.get("groq", ""), fallbacks=cfg.get("gemini_fallbacks"),
                             gemini_backup_keys=[bk] if isinstance(bk, str) else list(bk),
                             groq_fallbacks=cfg.get("groq_fallbacks"), lazy_gemini=True)
        self.cancel = threading.Event()
        self.agent = Agent(self.llm, self.memory, on_stage=on_stage or (lambda n: None), on_plan=lambda s: None,
                           notify=lambda t: None, cancelled=self.cancel.is_set,
                           research_cfg=dict(cfg.get("deep_research") or {}, documents=cfg.get("documents") or {}),
                           command_cfg=cfg.get("komut_hafizasi") or {})
        if confirm:
            fx.set_confirm_handler(confirm)
        fx.set_notify_handler(lambda text: self._log("action", text))
        fx.set_error_handler(self._record_error)
        fx.set_memory(self.memory)
        fx.set_search_keys(keys)
        try:
            fx.set_reminder_store(ReminderStore(self.memory.conn))
        except Exception:
            pass
        self.set_voice(voice)
        self.session_id = self.open_session()

    # -- yardımcılar
    def _log(self, kind, text):
        try:
            self.memory.log_event(kind, text)
        except Exception:
            pass

    def _record_error(self, where, detail):
        try:
            self.memory.log_error(where, detail)
        except Exception:
            pass

    def set_voice(self, on):
        """Yazılı sohbette araçlar konuşmaz; 'Sesli oku' açılırsa ses paketleri o an yüklenir."""
        self.voice = bool(on)
        self.fx._speak = self.fx._SPEAK_REAL if self.voice else (lambda *a, **k: None)

    def open_session(self):
        today = datetime.date.today()
        for s in self.memory.list_sessions(limit=40):
            if (s["title"] or "").startswith("Yan sohbet") and (s["updated"] or "").startswith(today.isoformat()):
                self.memory.current_session_id = s["id"]
                return s["id"]
        sid = self.memory.create_session("normal", "Yan sohbet")
        self.memory.rename_session(sid, f"Yan sohbet • {today.strftime('%d.%m.%Y')}")
        self.memory.current_session_id = sid
        return sid

    def history(self, limit=8):
        try:
            return [(r, c) for _, r, c in self.memory.get_session_messages(self.session_id, limit=limit)]
        except Exception:
            return []

    def mode_changed(self):
        try:
            self.llm.reset_mode_session()
        except Exception:
            pass

    def ask(self, text, mode_key):
        """Cevap metnini döner (hata olursa kısa bir açıklama). Çağıran bunu bir iş parçacığında çalıştırır."""
        mode_key = mode_key if mode_key in MODE_LABELS else "normal"
        mode_cfg = (self.cfg.get("modes") or {}).get(mode_key) or {}
        self.cancel.clear()
        try:
            self.memory.add_message("user", text, mode_key, session_id=self.session_id)
        except Exception as e:
            print(f"[YAN SOHBET] kayıt: {e}")
        try:
            answer = self.agent.handle(text, mode_key, mode_cfg)
            if isinstance(answer, dict):
                answer = answer.get("text", "") or answer.get("speak", "") or ""
            answer = answer or "Bir cevap üretemedim, tekrar dener misin?"
            ok = True
        except Exception as e:
            self._record_error("yan sohbet", f"{type(e).__name__}: {e}")
            answer = "Bir hata ile karşılaştım. Ayrıntıyı Geçmiş'teki notlara kaydettim."
            ok = False
        if ok:
            try:
                self.memory.add_message("assistant", answer, mode_key, session_id=self.session_id)
            except Exception as e:
                print(f"[YAN SOHBET] kayıt: {e}")
        return answer


# ------------------------------------------------------------------ pid / tek kopya
def write_pid():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PID_PATH, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def clear_pid():
    try:
        os.remove(PID_PATH)
    except OSError:
        pass


def render_plain(text):
    """Model cevabındaki markdown işaretlerini sade metne çevirir: [(parça, kalın_mı)]."""
    out = []
    lines = (text or "").split("\n")
    for i, line in enumerate(lines):
        st = line.strip()
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", st):
            line = ""
        elif re.match(r"^#{1,6}\s+", st):
            out.append((re.sub(r"^#{1,6}\s+", "", st).replace("**", ""), True))
            line = None
        if line is not None:
            line = re.sub(r"^(\s*)[*\-]\s+", r"\1• ", line)
            for j, part in enumerate(re.split(r"\*\*(.+?)\*\*", line)):
                if part:
                    out.append((part.replace("`", ""), bool(j % 2)))
        if i < len(lines) - 1:
            out.append(("\n", False))
    return out


# ------------------------------------------------------------------ pencere
def build_window(ctk, cfg, backend_factory, start_hidden=False):
    """Pencereyi kurar ve döner (test için: backend_factory(confirm, on_stage) -> Backend benzeri nesne)."""

    class MiniChat(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.cfg = cfg
            self.q = queue.Queue()
            self.backend = None
            self.busy = False
            self._confirm_event = threading.Event()
            self._confirm_value = {"v": False}
            from . import nobet
            self.ncfg = nobet.load_settings(cfg.get("nobet"))        # config + simgeden kaydedilen tercihler
            self.mode_key = self.ncfg.get("yan_sohbet_mod") if self.ncfg.get("yan_sohbet_mod") in MODE_LABELS else "normal"
            self.title("FENIX • Yan sohbet")
            self.configure(fg_color=BG)
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h = 400, 580
            self.geometry(f"{w}x{h}+{max(0, sw - w - 20)}+{max(0, sh - h - 70)}")
            self.minsize(340, 420)
            try:
                self.iconbitmap(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fenix.ico"))
            except Exception:
                pass
            self._pinned = True
            try:
                self.attributes("-topmost", True)
            except Exception:
                pass
            self._build()
            self.protocol("WM_DELETE_WINDOW", self.quit_chat)
            self.bind("<Escape>", lambda e: self.quit_chat())
            self.after(60, self._tick)
            self.after(500, self._poll_show)
            self.after(5000, self._poll_ram)
            self.after(50, lambda: threading.Thread(target=self._boot, daemon=True).start())
            if start_hidden:
                self.withdraw()

        # -- görünüm
        def _build(self):
            head = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
            head.pack(fill="x")
            ctk.CTkLabel(head, text="FENIX", text_color=CYAN, font=("Segoe UI", 15, "bold")).pack(side="left", padx=(12, 6), pady=8)
            self.mode_btn = ctk.CTkSegmentedButton(head, values=[i18n.tr(k) for k in MODES], command=self._on_mode, height=26,
                                                   fg_color=PANEL2, selected_color=EMERALD, selected_hover_color=CYAN,
                                                   unselected_color=PANEL2, font=("Segoe UI", 11))
            self.mode_btn.set(i18n.tr(MODE_LABELS[self.mode_key]))
            self.mode_btn.pack(side="left", padx=4)
            self.pin_btn = ctk.CTkButton(head, text="📌", width=30, height=26, fg_color=EMERALD, hover_color=CYAN,
                                         command=self._toggle_pin)
            self.pin_btn.pack(side="right", padx=(2, 10))
            self.ram_label = ctk.CTkLabel(head, text="", text_color=MUTED, font=("Segoe UI", 10))
            self.ram_label.pack(side="right", padx=4)

            self.chat = ctk.CTkTextbox(self, fg_color=BG, text_color=TEXT, font=("Segoe UI", 12), wrap="word",
                                       border_width=0)
            i18n.mark_raw(self.chat)
            self.chat.pack(fill="both", expand=True, padx=8, pady=(8, 4))
            tb = self.chat._textbox
            tb.tag_configure("user", foreground=CYAN, font=("Segoe UI", 11, "bold"))
            tb.tag_configure("fenix", foreground=EMERALD, font=("Segoe UI", 11, "bold"))
            tb.tag_configure("sys", foreground=AMBER)
            tb.tag_configure("b", font=("Segoe UI", 11, "bold"), foreground="#ffffff")
            self.chat.configure(state="disabled")

            self.status = ctk.CTkLabel(self, text="Hazırlanıyor…", text_color=MUTED, anchor="w", font=("Segoe UI", 10))
            self.status.pack(fill="x", padx=12)

            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=(2, 4))
            self.entry = ctk.CTkEntry(row, placeholder_text="Yaz ve Enter'a bas…", fg_color=PANEL, text_color=TEXT,
                                      border_color=PANEL2, height=34)
            self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.entry.bind("<Return>", lambda e: (self.send(), "break")[1])
            self.send_btn = ctk.CTkButton(row, text="Gönder", width=70, height=34, fg_color=EMERALD, hover_color=CYAN,
                                          command=self.send)
            self.send_btn.pack(side="right")

            foot = ctk.CTkFrame(self, fg_color="transparent")
            foot.pack(fill="x", padx=8, pady=(0, 8))
            self.voice_var = ctk.BooleanVar(value=bool(self.ncfg.get("yan_sohbet_sesli", False)))
            self.voice_chk = ctk.CTkCheckBox(foot, text="🔊 Sesli oku", variable=self.voice_var, command=self._on_voice,
                                             text_color=MUTED, fg_color=EMERALD, font=("Segoe UI", 11), height=20)
            self.voice_chk.pack(side="left")
            ctk.CTkButton(foot, text="Ana pencereyi aç", width=120, height=24, fg_color=PANEL2, hover_color=CYAN,
                          font=("Segoe UI", 11), command=self.open_main).pack(side="right")

        # -- olaylar
        def _on_mode(self, label):
            self.mode_key = {i18n.tr(k): v for k, v in MODES.items()}.get(label, "normal")
            self._remember_pref(yan_sohbet_mod=self.mode_key)
            if self.backend:
                self.backend.mode_changed()
            self.add("sys", f"{label} moda geçildi." + (" Bu modda işlem yapmam, sadece cevap veririm." if self.mode_key == "safe" else ""))

        def _toggle_pin(self):
            self._pinned = not self._pinned
            try:
                self.attributes("-topmost", self._pinned)
            except Exception:
                pass
            self.pin_btn.configure(fg_color=EMERALD if self._pinned else PANEL2)

        def _remember_pref(self, **kw):
            try:
                from . import nobet
                nobet.save_user_settings(**kw)
            except Exception:
                pass

        def _on_voice(self):
            self._remember_pref(yan_sohbet_sesli=bool(self.voice_var.get()))
            if self.backend:
                self.backend.set_voice(self.voice_var.get())

        def _poll_show(self):
            try:
                if os.path.exists(SHOW_PATH):
                    os.remove(SHOW_PATH)
                    self.deiconify()
                    self.lift()
                    self.focus_force()
                    self.entry.focus_set()
            except Exception:
                pass
            self.after(500, self._poll_show)

        def _poll_ram(self):
            try:
                from . import nobet
                mb = nobet._rss_mb()
                self.ram_label.configure(text=f"{mb} MB" if mb else "")
            except Exception:
                pass
            self.after(5000, self._poll_ram)

        # -- sohbet
        def add(self, who, text):
            self.chat.configure(state="normal")
            tb = self.chat._textbox
            prefix = {"user": i18n.tr("Sen"), "fenix": "FENIX", "sys": "•"}.get(who, who)
            tb.insert("end", f"\n{prefix}: ", who)
            if who != "user":
                text = i18n.tr(text, lines=(who == "sys"))
            if who == "user":
                tb.insert("end", text)
            else:
                for part, bold in render_plain(text):
                    tb.insert("end", part, "b" if bold else ())
            tb.insert("end", "\n")
            tb.see("end")
            self.chat.configure(state="disabled")

        def send(self):
            text = self.entry.get().strip()
            if not text or self.busy:
                return
            if not self.backend:
                self.add("sys", "Hâlâ hazırlanıyorum, birkaç saniye sonra tekrar dene.")
                return
            self.entry.delete(0, "end")
            self.add("user", text)
            self.busy = True
            self.send_btn.configure(state="disabled")
            self.status.configure(text="Düşünüyorum…")
            mode = self.mode_key

            def work():
                ans = self.backend.ask(text, mode)
                self.q.put(("answer", ans))
            threading.Thread(target=work, daemon=True).start()

        def _boot(self):
            try:
                self.backend = backend_factory(self._confirm, lambda name: self.q.put(("stage", name)))
                self.q.put(("ready", self.backend.history()))
            except Exception as e:
                self.q.put(("fatal", f"{type(e).__name__}: {e}"))

        # -- onay kutusu (araçlar çalışma iş parçacığından çağırır)
        def _confirm(self, title, message, detail=""):
            self._confirm_event.clear()
            self._confirm_value["v"] = False
            self.q.put(("confirm", (title, message, detail)))
            if not self._confirm_event.wait(timeout=120):
                self.q.put(("confirm_close", None))
                return False
            return self._confirm_value["v"]

        def _show_confirm(self, title, message, detail):
            dlg = ctk.CTkToplevel(self)
            dlg.title(title)
            dlg.configure(fg_color=BG)
            dlg.geometry("380x230")
            dlg.transient(self)
            self._dlg = dlg
            ctk.CTkLabel(dlg, text=title, text_color=AMBER, font=("Segoe UI", 14, "bold"), wraplength=340,
                         justify="left").pack(anchor="w", padx=16, pady=(14, 4))
            ctk.CTkLabel(dlg, text=message, text_color=TEXT, wraplength=340, justify="left",
                         font=("Segoe UI", 12)).pack(anchor="w", padx=16)
            if detail:
                ctk.CTkLabel(dlg, text=detail, text_color=MUTED, wraplength=340, justify="left",
                             font=("Segoe UI", 11)).pack(anchor="w", padx=16, pady=(6, 0))

            def answer(v):
                self._confirm_value["v"] = v
                self._confirm_event.set()
                dlg.destroy()
            r = ctk.CTkFrame(dlg, fg_color="transparent")
            r.pack(side="bottom", fill="x", padx=16, pady=14)
            ctk.CTkButton(r, text="Evet", width=100, fg_color=EMERALD, hover_color=CYAN, command=lambda: answer(True)).pack(side="left")
            ctk.CTkButton(r, text="Hayır", width=100, fg_color="#7f1d1d", hover_color="#b91c1c",
                          command=lambda: answer(False)).pack(side="left", padx=8)
            dlg.protocol("WM_DELETE_WINDOW", lambda: answer(False))
            dlg.after(60, lambda: (dlg.grab_set(), dlg.focus_force()))

        # -- kuyruk
        def _tick(self):
            try:
                while True:
                    kind, data = self.q.get_nowait()
                    if kind == "answer":
                        self.busy = False
                        self.send_btn.configure(state="normal")
                        self.status.configure(text="Hazır")
                        self.add("fenix", data)
                        if self.backend and self.backend.voice:
                            self._speak("".join(p for p, _ in render_plain(data)))      # ** # gibi işaretler okunmaz
                        self.entry.focus_set()
                    elif kind == "stage":
                        self.status.configure(text=f"{data}…")
                    elif kind == "ready":
                        self.status.configure(text="Hazır")
                        for role, content in data:
                            self.add("user" if role == "user" else "fenix" if role == "assistant" else "sys", content)
                        self.add("sys", f"Yan sohbet hazır ({MODE_LABELS[self.mode_key]} mod). Ana pencerede olan ekran görme "
                                        "ve dosya ekleme burada yok.")
                        self.entry.focus_set()
                    elif kind == "fatal":
                        self.status.configure(text="Başlatılamadı")
                        self.add("sys", "Yan sohbet başlatılamadı: " + data + "\nAnahtarların config.yaml'da olduğundan emin ol.")
                    elif kind == "confirm":
                        self._show_confirm(*data)
                    elif kind == "confirm_close":
                        try:
                            self._dlg.destroy()
                        except Exception:
                            pass
            except queue.Empty:
                pass
            self.after(60, self._tick)

        def _speak(self, text):
            def run():
                try:
                    from . import audio_io
                    audio_io.speak(text, (cfg.get("audio") or {}).get("tts_voice", "tr-TR-AhmetNeural"))
                except Exception as e:
                    print(f"[YAN SOHBET] ses: {e}")
            threading.Thread(target=run, daemon=True).start()

        # -- çıkış
        def open_main(self):
            try:
                import subprocess
                from . import nobet
                subprocess.Popen([nobet.python_exe(), os.path.join(nobet.project_dir(), "app.py")], cwd=nobet.project_dir(),
                                 creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)
            except Exception as e:
                self.add("sys", f"Ana pencere açılamadı: {e}")
                return
            self.quit_chat()

        def quit_chat(self):
            clear_pid()
            try:
                self.destroy()
            finally:
                os._exit(0)

    return MiniChat()


def main():
    """nobet_main.py --sohbet"""
    import yaml
    import customtkinter as ctk
    from .killswitch import KillSwitch
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}
    from . import i18n
    i18n.init(cfg)
    i18n.install_tk_hooks()
    write_pid()
    ks = cfg.get("killswitch") or {}
    KillSwitch(ks.get("hotkey", "ctrl+alt+q"), ks.get("corner_trigger", True), ks.get("corner_size", 5),
               ks.get("corner_hold_seconds", 1.5), light=True, on_quit=clear_pid).start()
    ctk.set_appearance_mode("dark")

    from . import nobet
    voice_on = bool(nobet.load_settings(cfg.get("nobet")).get("yan_sohbet_sesli", False))

    def factory(confirm, on_stage):
        return Backend(cfg, confirm=confirm, on_stage=on_stage, voice=voice_on)
    app = build_window(ctk, cfg, factory)
    try:
        app.mainloop()
    finally:
        clear_pid()
