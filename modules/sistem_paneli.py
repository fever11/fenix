# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""🖥️ Sistem paneli (v1.4, Mustafa'nın fikri; OMEN Gaming Hub'daki "System Vitals" ekranından esinlendi).

Tek pencerede:
  • Durum: CPU / RAM / ekran kartı halkaları, diskler, ağ hızı, pil, en çok kaynak kullanan programlar (onaylı Kapat)
  • Sağlık raporu: disk, bellek, pil sağlığı, açılış programları, son güvenlik olayları, en büyük dosyalar
  • İşlem defteri: FENIX'in yaptığı değişiklikler, her satırda "Geri al"; FENIX çöp kutusu
  • Güvenlik olayları: Nöbet uyarılarının listesi
  • Üstte kısayollar: Geçmiş, Raporlar, İstatistik, Ayarlar, Eklentiler, Yetenekler, Öğrendiklerim
Veriler arka planda okunur (pencere donmaz); yapay zekâ ve internet kullanılmaz.
"""
import os
import queue
import threading
import time
import tkinter as tk

import customtkinter as ctk

from . import sistem_bilgi as SB

BG, PANEL, PANEL2 = "#04070d", "#060c16", "#0b1522"
ACCENT, CYAN, AMBER, RED, GREEN = "#38bdf8", "#7dd3fc", "#fbbf24", "#f87171", "#34d399"
TEXT, MUTED = "#dbe7f3", "#8aa0b6"
YENILEME_MS = 2000


_VURGU = {"renk": ACCENT, "hover": CYAN}       # seçili modun rengi (Güvenli/Normal/Devil); panel açılınca alınır


def renk(yuzde):
    if yuzde is None:
        return MUTED
    return RED if yuzde >= 90 else AMBER if yuzde >= 75 else _VURGU["renk"]


class Halka(ctk.CTkFrame):
    """Yuvarlak gösterge: ortada yüzde, altında açıklama."""

    def __init__(self, master, baslik, boyut=150):
        super().__init__(master, fg_color=PANEL2, corner_radius=10)
        ctk.CTkLabel(self, text=baslik, text_color=TEXT, font=("Segoe UI", 13, "bold"), anchor="w").pack(
            fill="x", padx=12, pady=(10, 0))
        self.b = boyut
        self.c = tk.Canvas(self, width=boyut, height=boyut, bg=PANEL2, highlightthickness=0)
        self.c.pack(pady=(4, 2))
        self.alt = ctk.CTkLabel(self, text="", text_color=MUTED, font=("Segoe UI", 11))
        self.alt.pack(pady=(0, 2))
        self.ek = ctk.CTkLabel(self, text="", text_color=GREEN, font=("Segoe UI", 13, "bold"))
        self.ek.pack(pady=(0, 10))
        self.ayarla(None, "okunuyor…")

    def ayarla(self, yuzde, alt="", ek="", ek_renk=GREEN):
        c, b, k = self.c, self.b, 12
        c.delete("all")
        c.create_oval(k, k, b - k, b - k, outline="#16263a", width=k)
        if yuzde is not None:
            c.create_arc(k, k, b - k, b - k, start=90, extent=-3.6 * max(0.0, min(100.0, yuzde)), style="arc",
                         outline=renk(yuzde), width=k)
            c.create_text(b / 2, b / 2 - 6, text=f"{yuzde:.0f}%", fill=TEXT, font=("Segoe UI", 24, "bold"))
        else:
            c.create_text(b / 2, b / 2 - 6, text="—", fill=MUTED, font=("Segoe UI", 24, "bold"))
        c.create_text(b / 2, b / 2 + 22, text="kullanım", fill=MUTED, font=("Segoe UI", 9))
        self.alt.configure(text=alt)
        self.ek.configure(text=ek, text_color=ek_renk)


class SistemPaneli(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("FENIX • Sistem")
        self.configure(fg_color=BG)
        self.geometry("980x700")
        self.minsize(820, 560)
        self.q = queue.Queue()
        self._kapandi = False
        self._vurgu_al()
        self._okuyor = False
        self._kisayollar()
        self.tabs = ctk.CTkTabview(self, fg_color=PANEL, segmented_button_selected_color=_VURGU["renk"],
                                   segmented_button_selected_hover_color=_VURGU["hover"], text_color=TEXT)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        for ad in ("Durum", "Sağlık raporu", "İşlem defteri", "Güvenlik olayları"):
            self.tabs.add(ad)
        self._durum_kur(self.tabs.tab("Durum"))
        self._saglik_kur(self.tabs.tab("Sağlık raporu"))
        self._defter_kur(self.tabs.tab("İşlem defteri"))
        self._olay_kur(self.tabs.tab("Güvenlik olayları"))
        self.protocol("WM_DELETE_WINDOW", self.kapat)
        self.after(100, self._dongu)
        self.after(150, self._kuyruk)

    # ------------------------------------------------------------- üst kısayollar
    def _kisayollar(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(10, 0))
        a = self.app
        dugmeler = [("📜 Geçmiş", "_show_history"), ("📄 Raporlar", "_show_reports"),
                    ("📊 İstatistik", "_show_stats"), ("⚙️ Ayarlar", "_show_settings"),
                    ("🧩 Eklentiler", "_show_plugins"), ("🧠 Yetenekler", "_show_skills"),
                    ("🎓 Öğrendiklerim", "_show_learned"), ("🧪 Oyun alanı", "_show_lab")]
        for yazi, ad in dugmeler:
            fn = getattr(a, ad, None)
            if fn is None or (ad == "_show_lab" and not getattr(a, "_ogrenme_var", False)):
                continue
            ctk.CTkButton(row, text=yazi, command=fn, fg_color=PANEL2, hover_color=CYAN, text_color=TEXT, height=28,
                          width=10, font=("Segoe UI", 11)).pack(side="left", padx=2)

    # ------------------------------------------------------------- Durum
    def _durum_kur(self, t):
        ust = ctk.CTkFrame(t, fg_color="transparent")
        ust.pack(fill="x")
        self.h_cpu = Halka(ust, "CPU")
        self.h_ram = Halka(ust, "RAM")
        self.h_gpu = Halka(ust, "Ekran kartı")
        for h in (self.h_cpu, self.h_ram, self.h_gpu):
            h.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        depo = ctk.CTkFrame(ust, fg_color=PANEL2, corner_radius=10)
        depo.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        ctk.CTkLabel(depo, text="Depolama", text_color=TEXT, font=("Segoe UI", 13, "bold"), anchor="w").pack(
            fill="x", padx=12, pady=(10, 4))
        self.depo_kutu = ctk.CTkFrame(depo, fg_color="transparent")
        self.depo_kutu.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        alt = ctk.CTkFrame(t, fg_color="transparent")
        alt.pack(fill="both", expand=True)
        sol = ctk.CTkFrame(alt, fg_color="transparent", width=230)
        sol.pack(side="left", fill="y", padx=0)
        ag = ctk.CTkFrame(sol, fg_color=PANEL2, corner_radius=10)
        ag.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(ag, text="Ağ", text_color=TEXT, font=("Segoe UI", 13, "bold"), anchor="w").pack(
            fill="x", padx=12, pady=(10, 0))
        self.ag_l = ctk.CTkLabel(ag, text="—", text_color=TEXT, font=("Segoe UI", 18, "bold"), justify="left",
                                 anchor="w")
        self.ag_l.pack(fill="x", padx=12, pady=(2, 10))
        pil = ctk.CTkFrame(sol, fg_color=PANEL2, corner_radius=10)
        pil.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(pil, text="Pil", text_color=TEXT, font=("Segoe UI", 13, "bold"), anchor="w").pack(
            fill="x", padx=12, pady=(10, 0))
        self.pil_l = ctk.CTkLabel(pil, text="okunuyor…", text_color=TEXT, font=("Segoe UI", 12), justify="left",
                                  anchor="w")
        self.pil_l.pack(fill="x", padx=12, pady=(2, 10))

        prog = ctk.CTkFrame(alt, fg_color=PANEL2, corner_radius=10)
        prog.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        bas = ctk.CTkFrame(prog, fg_color="transparent")
        bas.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bas, text="En çok kaynak kullanan programlar", text_color=TEXT,
                     font=("Segoe UI", 13, "bold")).pack(side="left")
        self.sirala = ctk.CTkSegmentedButton(bas, values=["RAM", "CPU"], height=24, font=("Segoe UI", 11),
                                             selected_color=_VURGU["renk"], unselected_color=PANEL)
        self.sirala.set("RAM")
        self.sirala.pack(side="right")
        self.prog_kutu = ctk.CTkFrame(prog, fg_color="transparent")
        self.prog_kutu.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        # Satırlar bir kez kurulur, sonra sadece yazıları güncellenir (her 2 sn'de yeniden kurmak titretiyordu ve
        # "Kapat"a basarken düğme yok olabiliyordu)
        self._prog_satir = []
        for i in range(6):
            satir = ctk.CTkFrame(self.prog_kutu, fg_color="transparent")
            ad = ctk.CTkLabel(satir, text="", text_color=TEXT, font=("Segoe UI", 11), anchor="w", width=240)
            ad.pack(side="left")
            ram = ctk.CTkLabel(satir, text="", text_color=MUTED, font=("Segoe UI", 11), width=80)
            ram.pack(side="left")
            cpu = ctk.CTkLabel(satir, text="", text_color=MUTED, font=("Segoe UI", 11), width=70)
            cpu.pack(side="left")
            ctk.CTkButton(satir, text="Kapat", width=60, height=22, fg_color="#3b1220", hover_color="#7f1d1d",
                          font=("Segoe UI", 10), command=lambda i=i: self._satir_kapat(i)).pack(side="right")
            self._prog_satir.append({"cerceve": satir, "ad": ad, "ram": ram, "cpu": cpu, "veri": None})
        self._disk_sayisi = -1

    def _dongu(self):
        if self._kapandi:
            return
        if not self._okuyor:
            self._okuyor = True
            sira = "cpu" if self.sirala.get() == "CPU" else "ram"

            def oku():
                try:
                    v = {"anlik": SB.anlik(), "prog": SB.en_cok_kullananlar(6, sira), "pil": SB.pil()}
                except Exception as e:
                    v = {"hata": str(e)}
                self.q.put(("durum", v))
            threading.Thread(target=oku, daemon=True).start()
        self.after(YENILEME_MS, self._dongu)

    def _kuyruk(self):
        if self._kapandi:
            return
        try:
            while True:
                tur, v = self.q.get_nowait()
                if tur == "durum":
                    self._okuyor = False
                    self._durum_goster(v)
                elif tur == "rapor":
                    self._rapor_goster(v)
                elif tur == "defter":
                    self._defter_yenile()
                elif tur == "mesaj":
                    from tkinter import messagebox
                    messagebox.showinfo("FENIX", v, parent=self)
        except queue.Empty:
            pass
        self.after(150, self._kuyruk)

    def _durum_goster(self, v):
        if "hata" in v:
            return
        a = v["anlik"]
        self.h_cpu.ayarla(a["cpu"], f"{os.cpu_count() or '?'} çekirdek")
        r = a["ram"]
        self.h_ram.ayarla(r["yuzde"] if r else None, f"{r['kullanilan_gb']} / {r['toplam_gb']} GB" if r else "")
        g = a["gpu"]
        if g:
            sic = g["sicaklik"]
            self.h_gpu.ayarla(g["yuzde"], g["ad"][:28], f"{sic:.0f} °C",
                              ek_renk=RED if sic >= 85 else AMBER if sic >= 75 else GREEN)
        else:
            self.h_gpu.ayarla(None, "NVIDIA kartı bulunamadı")
        if len(a["diskler"]) != self._disk_sayisi:
            for w in self.depo_kutu.winfo_children():
                w.destroy()
            self._disk_w = []
            for _ in a["diskler"]:
                l = ctk.CTkLabel(self.depo_kutu, text="", text_color=MUTED, font=("Segoe UI", 11), anchor="w")
                l.pack(fill="x", pady=(6, 0))
                pb = ctk.CTkProgressBar(self.depo_kutu, height=10, fg_color="#16263a")
                pb.pack(fill="x")
                self._disk_w.append((l, pb))
            self._disk_sayisi = len(a["diskler"])
        for d, (l, pb) in zip(a["diskler"], self._disk_w):
            l.configure(text=f"{d['ad']}   %{d['yuzde']:.0f} · {d['bos_gb']} GB boş / {d['toplam_gb']} GB")
            pb.configure(progress_color=renk(d["yuzde"]))
            pb.set(d["yuzde"] / 100)
        n = a["ag"]
        self.ag_l.configure(text=(f"↑ {n['yukleme']} Mbit/sn\n↓ {n['indirme']} Mbit/sn") if n else "—")
        p = v["pil"]
        if p:
            s = p.get("saglik")
            self.pil_l.configure(text=f"%{p['yuzde']} · {'prizde' if p['prizde'] else 'pilde'}"
                                      + (f"\nSağlık: %{s['yuzde']}" if s else ""))
        else:
            self.pil_l.configure(text="Pil yok (masaüstü)")
        for i, s in enumerate(self._prog_satir):
            pr = v["prog"][i] if i < len(v["prog"]) else None
            s["veri"] = pr
            if not pr:
                s["cerceve"].pack_forget()
                continue
            s["ad"].configure(text=pr["ad"] + (f" ({pr['adet']})" if pr["adet"] > 1 else ""))
            s["ram"].configure(text=f"{pr['ram_mb']} MB")
            s["cpu"].configure(text=f"%{pr['cpu']:.0f} CPU")
            if not s["cerceve"].winfo_ismapped():
                s["cerceve"].pack(fill="x", pady=1)

    def _satir_kapat(self, i):
        pr = self._prog_satir[i]["veri"]
        if pr:
            self._kapat(pr["pid"], pr["ad"])

    def _kapat(self, pid, ad):
        """Onaylı süreç sonlandırma (FENIX'in güvenlik kuralları: Windows çekirdek süreçleri kapatılmaz)."""
        def is_():
            from . import functions as fx
            r = fx.stop_process(pid, reason="Sistem panelinden")
            if r.get("status") == "ok":
                try:
                    from . import islem_defteri as DEF
                    DEF.kaydet("komut", f"{ad} programı kapatıldı (Sistem paneli)", "", None)
                except Exception:
                    pass
            if r.get("status") not in ("ok", "cancelled"):
                self.q.put(("mesaj", r.get("message", "Kapatılamadı.")))
        threading.Thread(target=is_, daemon=True).start()

    # ------------------------------------------------------------- Sağlık raporu
    def _saglik_kur(self, t):
        row = ctk.CTkFrame(t, fg_color="transparent")
        row.pack(fill="x", pady=(4, 6))
        self.rapor_btn = ctk.CTkButton(row, text="🩺 Raporu oluştur", command=self._rapor_olustur,
                                       fg_color=_VURGU["renk"], hover_color=_VURGU["hover"], text_color="#001018",
                                       height=30)
        self.rapor_btn.pack(side="left")
        ctk.CTkButton(row, text="Kopyala", command=self._rapor_kopyala, fg_color=PANEL2, hover_color=CYAN,
                      height=30, width=90).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="Yerel okuma; yapay zekâ ve internet kullanılmaz. En büyük dosyaları bulmak birkaç "
                               "saniye sürebilir.", text_color=MUTED, font=("Segoe UI", 11)).pack(side="left", padx=8)
        self.rapor_kutu = ctk.CTkTextbox(t, fg_color=PANEL2, text_color=TEXT, font=("Consolas", 12), wrap="word")
        self.rapor_kutu.pack(fill="both", expand=True)
        self.rapor_kutu.insert("end", "\"Raporu oluştur\"a bas.")
        self.rapor_kutu.configure(state="disabled")

    def _rapor_olustur(self):
        self.rapor_btn.configure(state="disabled", text="Hazırlanıyor…")
        threading.Thread(target=lambda: self.q.put(("rapor", SB.saglik_raporu())), daemon=True).start()

    def _rapor_goster(self, metin):
        self.rapor_btn.configure(state="normal", text="🩺 Raporu oluştur")
        self.rapor_kutu.configure(state="normal")
        self.rapor_kutu.delete("1.0", "end")
        self.rapor_kutu.insert("end", metin)
        self.rapor_kutu.configure(state="disabled")

    def _rapor_kopyala(self):
        self.clipboard_clear()
        self.clipboard_append(self.rapor_kutu.get("1.0", "end").strip())

    # ------------------------------------------------------------- İşlem defteri
    def _defter_kur(self, t):
        row = ctk.CTkFrame(t, fg_color="transparent")
        row.pack(fill="x", pady=(4, 6))
        ctk.CTkButton(row, text="Yenile", command=self._defter_yenile, fg_color=PANEL2, hover_color=CYAN,
                      height=28, width=80).pack(side="left")
        self.cop_l = ctk.CTkLabel(row, text="", text_color=MUTED, font=("Segoe UI", 11))
        self.cop_l.pack(side="left", padx=10)
        ctk.CTkButton(row, text="Çöpü şimdi boşalt", command=self._cop_bosalt, fg_color="#3b1220",
                      hover_color="#7f1d1d", height=28).pack(side="right")
        self.defter_kutu = ctk.CTkScrollableFrame(t, fg_color=PANEL2)
        self.defter_kutu.pack(fill="both", expand=True)
        self._defter_yenile()

    def _defter_yenile(self):
        from . import islem_defteri as DEF
        for w in self.defter_kutu.winfo_children():
            w.destroy()
        kayitlar = [k for k in DEF.oku() if k.get("tur") != "geri_alma"][-150:]
        if not kayitlar:
            ctk.CTkLabel(self.defter_kutu, text="Henüz bir işlem yok.", text_color=MUTED).pack(pady=20)
        for k in reversed(kayitlar):
            s = ctk.CTkFrame(self.defter_kutu, fg_color="transparent")
            s.pack(fill="x", pady=1)
            ctk.CTkLabel(s, text=time.strftime("%d.%m %H:%M", time.localtime(k["zaman"])), text_color=MUTED,
                         font=("Consolas", 11), width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(s, text=DEF.TUR_ADI.get(k["tur"], k["tur"]), text_color=CYAN, font=("Segoe UI", 11),
                         width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(s, text=k["ozet"][:90], text_color=TEXT, font=("Segoe UI", 11), anchor="w").pack(
                side="left", fill="x", expand=True)
            if k.get("geri_alindi"):
                ctk.CTkLabel(s, text="geri alındı", text_color=MUTED, font=("Segoe UI", 10), width=80).pack(side="right")
            elif k.get("geri"):
                ctk.CTkButton(s, text="Geri al", width=70, height=22, fg_color=PANEL, hover_color=CYAN,
                              font=("Segoe UI", 10), command=lambda i=k["id"]: self._geri_al(i)).pack(side="right")
            else:
                ctk.CTkLabel(s, text="geri alınamaz", text_color=MUTED, font=("Segoe UI", 10), width=80).pack(side="right")
        try:
            mb = DEF.cop_boyutu() / 1024 / 1024
            self.cop_l.configure(text=f"FENIX çöp kutusu: {mb:.1f} MB · {DEF.SAKLAMA_GUN} gün sonra kendiliğinden silinir")
        except Exception:
            pass

    def _geri_al(self, kayit_id):
        def is_():
            from . import functions as fx
            from . import islem_defteri as DEF
            r = DEF.geri_al(kayit_id, onayla=fx._confirm)
            if r.get("status") not in ("ok", "cancelled"):
                self.q.put(("mesaj", r.get("message", "Geri alınamadı.")))
            self.q.put(("defter", None))
        threading.Thread(target=is_, daemon=True).start()

    def _cop_bosalt(self):
        def is_():
            from . import functions as fx
            from . import islem_defteri as DEF
            if fx._confirm("FENIX çöp kutusu boşaltılacak", "Çöp kutusundaki her şey KALICI olarak silinsin mi?",
                           "Bunlar FENIX'in sildiği dosyalar ve üzerine yazılan dosyaların eski hâlleri. Boşaltınca "
                           "bu işlemler bir daha geri alınamaz."):
                n = DEF.cop_temizle(gun=-1)
                self.q.put(("mesaj", f"{n} öğe kalıcı olarak silindi."))
                self.q.put(("defter", None))
        threading.Thread(target=is_, daemon=True).start()

    # ------------------------------------------------------------- Güvenlik olayları
    def _olay_kur(self, t):
        ctk.CTkButton(t, text="Yenile", command=self._olay_yenile, fg_color=PANEL2, hover_color=CYAN, height=28,
                      width=80).pack(anchor="w", pady=(4, 6))
        self.olay_kutu = ctk.CTkTextbox(t, fg_color=PANEL2, text_color=TEXT, font=("Segoe UI", 12), wrap="word")
        self.olay_kutu.pack(fill="both", expand=True)
        self._olay_yenile()

    def _olay_yenile(self):
        olaylar = SB.son_olaylar(50)
        self.olay_kutu.configure(state="normal")
        self.olay_kutu.delete("1.0", "end")
        if not olaylar:
            self.olay_kutu.insert("end", "Kayıtlı güvenlik olayı yok. Nöbet ve pencere açıkken çalışan gözcü "
                                         "uyarıları burada listelenir.")
        for o in olaylar:
            isaret = {"kritik": "🔴", "dikkat": "🟠"}.get(o.get("seviye"), "🔵")
            self.olay_kutu.insert("end", f"{isaret} {time.strftime('%d.%m.%Y %H:%M', time.localtime(o['zaman']))}  "
                                         f"{o.get('baslik') or ''}\n    {o.get('kisa') or ''}\n\n")
        self.olay_kutu.configure(state="disabled")

    def _vurgu_al(self):
        try:
            _VURGU.update(renk=self.app._accent(), hover=self.app._accent_hover())
        except Exception:
            pass

    def mod_rengi(self):
        """Ana pencerede mod değişince çağrılır: panelin vurgu rengi moda uyar."""
        self._vurgu_al()
        v, h = _VURGU["renk"], _VURGU["hover"]
        try:
            self.tabs.configure(segmented_button_selected_color=v, segmented_button_selected_hover_color=h)
            self.sirala.configure(selected_color=v)
            self.rapor_btn.configure(fg_color=v, hover_color=h)
        except Exception:
            pass                      # halkalar ve çubuklar bir sonraki yenilemede (2 sn) yeni rengi alır

    def refresh(self):
        self._defter_yenile()
        self._olay_yenile()

    def kapat(self):
        self._kapandi = True
        self.destroy()
