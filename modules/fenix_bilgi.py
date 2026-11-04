# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Kendini tanı (v1.2.1).

FENIX'in modeli FENIX'in kodunu göremez; kendisi sorulunca tahmin ediyordu (04.11 testi: modları dosya adlarıyla
karıştırdı, "OpenAI/Claude ile çalışırım", "veriler dışarı çıkmaz" dedi). Bu araç, FENIX'in kendisi hakkındaki
bilgileri O ANKİ gerçek durumdan okur: sürüm, config.yaml'daki modlar ve modeller, açık eklentiler, yüklü araçlar,
ayarlar. Sabit metin sadece kodda değişmeyen gerçekler (gizlilik, sınırlar) için kullanılır.
"""
import os
import glob
import re

from . import functions as fx

CFG = {}
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # proje klasörü

BOLUMLER = ("kimlik", "modlar", "modeller", "yetenekler", "hafiza", "eklentiler", "arayuz", "guvenlik", "sinirlar")

MOD_ACIKLAMA = {
    "safe": "sadece okur ve sohbet eder; dosya yazma, silme, ayar değiştirme gibi değiştiren araçlar kapalı, yalnızca "
            "salt okunur araçlar açık",
    "normal": "günlük işler; değiştiren araçlar açık, riskli olanlar (silme, üzerine yazma, riskli komut) onay kutusuyla",
    "devil": "derin araştırma (plan, çok kaynak, kaynaklı rapor) ve uzun, çok adımlı işler; kritik işlemlerde yine onay",
    "ogrenme": "özel sürüm: öğrenme deneyleri için",
}

KATEGORI = [
    ("Dosya ve belge", ["find_files", "list_folder", "read_file", "write_file", "edit_file", "delete_file",
                        "open_folder_by_name", "export_report"],
     "write_file .txt/kod dosyası ve gerçek Word (.docx) / PDF belgesi yazar; delete_file Geri Dönüşüm Kutusu'na taşır"),
    ("Web", ["search_web", "read_webpage", "open_url", "check_link", "inspect_website_security", "cookie_guard"],
     "check_link sahte site/bağlantı kontrolü yapar"),
    ("Bilgisayar kontrolü", ["adjust_volume", "set_system_volume", "set_brightness", "set_radio", "media_control",
                             "power_action", "window_action", "open_app_by_name", "close_app", "close_front_app",
                             "list_installed_apps", "run_command"],
     "run_command PowerShell çalıştırır, riskli komutlar onay ister"),
    ("Ekran", ["look_at_screen", "pc_awareness"], "ekranı görür ve anlatır (Gemini ile); ekranda tıklama/yazma YOK"),
    ("Hatırlatma ve kısayol", ["set_reminder", "list_reminders", "cancel_reminder", "save_shortcut",
                               "list_shortcuts", "delete_shortcut"],
     "kısayol: tek cümleyle birden çok iş (ör. 'çalışma modu')"),
    ("Güvenlik", ["scan_pc", "find_suspicious_processes", "network_connections", "watch_startup_programs",
                  "remove_startup_program", "restore_startup_program", "stop_process", "check_windows_security",
                  "enable_protection", "check_project_security", "scan_project", "inspect_system"],
     "müdahaleler (süreç durdurma, başlangıçtan kaldırma) sadece kullanıcı isteyince ve onayla"),
    ("Ses ve hafıza", ["set_voice", "forget"], "set_voice FENIX'in konuşma sesi; forget 'bunu unut'"),
]


def _cfg():
    return CFG or {}


def _anahtar_var(ad):
    return bool(str((_cfg().get("api_keys") or {}).get(ad) or "").strip())


def _tur_siniri(mod):
    return 12 if mod == "devil" else 8 if mod == "ogrenme" else 6


def _kimlik():
    from .version import VERSION
    diller = ["Türkçe"] + [{"en": "İngilizce", "de": "Almanca", "ru": "Rusça", "fr": "Fransızca", "es": "İspanyolca"}.get(
        os.path.splitext(os.path.basename(p))[0], os.path.basename(p)) for p in sorted(glob.glob(os.path.join(KOK, "locales", "*.json")))]
    testler = bool(glob.glob(os.path.join(KOK, "tests", "test_*.py")))
    return [f"Ad: FENIX, sürüm {VERSION}. Geliştirici: Mustafa Koç (çekirdek: MK-Agentic-System).",
            "Tür: Windows için Python masaüstü asistanı (CustomTkinter arayüz), kullanıcının kendi bilgisayarında çalışır; "
            "bir şirketin bulut ürünü değil, tek kişilik bir proje.",
            "Arayüz dilleri: " + ", ".join(dict.fromkeys(diller)) + ".",
            "Lisans: GNU GPL v3 (GPL-3.0-only) ve ek şartlar (NOTICE.md): herkes kullanabilir, değiştirebilir, paylaşabilir; "
            "ama aynı lisansla, Mustafa Koç'un adı korunarak, başka bir adla ve kendi eseri gibi sunmadan. Garanti yoktur. "
            "Resmi kaynak: github.com/fever11/fenix.",
            ("Otomatik test paketi var (tests/ klasörü; her güncellemede GitHub Actions'ta çalışır)." if testler else
             "Bu kurulumda test klasörü yok.")]


def _modlar():
    out = []
    for k, m in (_cfg().get("modes") or {}).items():
        out.append(f"{m.get('label', k)} ({k}): model {m.get('groq_model', '?')}, en fazla {_tur_siniri(k)} araç adımı; "
                   f"{MOD_ACIKLAMA.get(k, '')}.")
    out.append("İş seçili moda göre büyükse FENIX başlamadan ya da sonunda daha uygun modu önerir; mod, kullanıcı "
               "'evet' demeden değişmez. Mod değişince sohbet korunur.")
    return out


def _modeller():
    c = _cfg()
    modlar = c.get("modes") or {}
    sohbet = sorted({m.get("groq_model") for m in modlar.values() if m.get("groq_model")})
    out = [f"Sohbet ve araçlar: Groq üzerinden açık kaynak modeller ({', '.join(sohbet)}). Groq anahtarı: "
           f"{'girilmiş' if _anahtar_var('groq') else 'yok'}.",
           "Groq yedekleri (günlük sınır dolarsa): " + (", ".join(c.get("groq_fallbacks") or []) or "yok") + "."]
    nv = (c.get("nvidia") or {}).get("chat_models") or []
    out.append("NVIDIA yedeği: " + (", ".join(nv) if nv and _anahtar_var("nvidia") else
                                     ("tanımlı ama anahtar yok" if nv else "yok")) + ".")
    gm = sorted({m.get("gemini_model") for m in modlar.values() if m.get("gemini_model")})
    out.append(f"Google Gemini ({', '.join(gm + list(c.get('gemini_fallbacks') or []))}): ekranı ve resimleri görme, "
               f"anlamsal hafıza (embedding), Groq/NVIDIA çalışmazsa son yedek. Gemini anahtarı: "
               f"{'girilmiş' if _anahtar_var('gemini') else 'yok'}.")
    fm = (c.get("deep_research") or {}).get("fast_model")
    if fm:
        out.append(f"Derin araştırmada plan ve not çıkarma için hızlı model: {fm}.")
    out.append("OpenAI, Anthropic (Claude) gibi şirketlerin API'leri KULLANILMIYOR. (FENIX geliştirilirken kodlama "
               "yardımcısı olarak Claude kullanıldı; çalışırken FENIX Claude'a bağlanmaz.)")
    return out


def _yetenekler():
    var = set(fx.WHITELISTED_FUNCTIONS)
    out, kullanilan = [], set()
    for ad, araclar, not_ in KATEGORI:
        bu = [a for a in araclar if a in var]
        kullanilan |= set(bu)
        if bu:
            out.append(f"{ad}: {', '.join(bu)}. {not_[0].upper() + not_[1:]}.")
    out.append("Derin araştırma (Devil mod): plan çıkarır, 12+ sayfa okur, notları birleştirip kaynaklı rapor yazar; "
               "raporlar Raporlar penceresinde, Word/PDF olarak dışa aktarılabilir.")
    diger = sorted(a for a in var - kullanilan if not a.startswith(("mcp_", "lab_")) and a not in
                   ("eklentileri_listele", "fenix_hakkinda"))
    if diger:
        out.append("Diğer araçlar: " + ", ".join(diger) + ".")
    return out


def _hafiza():
    mem = (_cfg().get("memory") or {})
    try:
        from . import user_settings, yol_hafizasi as yh
        yol = f"açık ({len(yh.yollar())} yol, {len(yh.projeler())} proje)" if yh.acik() else "kapalı"
    except Exception:
        yol = "bilinmiyor"
    return [f"Sohbetler ve notlar: yerel SQLite veritabanı ({mem.get('db_path', 'data/fenix_memory.db')}). Kalıcıdır, "
            "FENIX kapanınca silinmez; eski sohbetlerden ilgili kayıtlar yeni sohbete bağlam olarak gelir.",
            f"Anlamsal hafıza: ChromaDB ({mem.get('chroma_path', 'data/chroma_db')}); metinler Gemini embedding ile "
            "vektöre çevrilir (bunun için metin Google'a gönderilir).",
            "'not al: ...' not ekler; 'bunu unut' (forget) ilgili kayıtları siler; gizli sohbette hiçbir şey kaydedilmez.",
            "Komut hafızası: başarılı kısa tek-araçlı komutları ('ses aç') öğrenir, sonra modele sormadan yapar "
            "(Öğrendiklerim penceresi).",
            f"Yol hafızası: bir işte bulduğu araç yolunu hatırlar, benzer işi daha az adımla yapar; şu an {yol}.",
            "Ortak sohbet: ekran (Gemini), derin araştırma, komut hafızası ve mod değişimi arasında konuşma korunur; "
            "'Yeni sohbet' sıfırlar."]


def _eklentiler():
    out = ["Eklentiler (MCP) Eklentiler penceresinden config.yaml düzenlemeden açılıp kapanır; anahtar gerekenlerin "
           "anahtarı pencereden girilir. Salt okunur eklenti araçları onaysız, yazan/silen araçlar onay kutusuyla "
           "çalışır; Güvenli modda sadece salt okunurlar. Kullanıcı kendi eklentisini (npm paketi) ekleyebilir, onun "
           "her işlemi onay ister."]
    try:
        from . import mcp_eklenti as mx
        out.append("Hazır katalog: " + ", ".join(k["baslik"] for k in mx.KATALOG) + ".")
        durum = mx.durum_metni().splitlines()
        sunucular = [d.strip("• ").strip() for d in durum if d.startswith("  • ")]
        out.append("Şu anki durum: " + ("; ".join(sunucular) if sunucular else durum[0] if durum else "eklenti yok") + ".")
    except Exception:
        out.append("Eklenti modülü bu kurulumda yok.")
    return out


def _arayuz():
    c = _cfg()
    ks = (c.get("killswitch") or {})
    nb = (c.get("nobet") or {})
    try:
        from . import ogrenme  # noqa: F401
        ozel = True
    except Exception:
        ozel = False
    menu = ["Geçmiş", "Raporlar", "Hatırlatma", "Yetenekler", "Eklentiler", "Öğrendiklerim", "İstatistik"] + \
           (["Oyun alanı (özel sürüm)"] if ozel else []) + ["Nöbete geç", "Ayarlar"]
    return ["Ana pencere: solda sohbet listesi, mod seçimi ve menü; ortada görev paneli (adım adım ne yapıldığı) ve "
            "Bas-Konuş; sağda sohbet. Dosya sürükleyip eklenir, Ctrl+V ile görsel yapıştırılır; Sesli cevap açılıp "
            "kapanır (tercih hatırlanır).",
            "Menü pencereleri: " + ", ".join(menu) + ".",
            f"Nöbet modu: ana pencere kapalıyken sistem tepsisinde bilgisayarı izler; yan sohbet: "
            f"{str(nb.get('yan_sohbet_kisayol', 'ctrl+alt+j')).title()}.",
            f"Acil kapatma: {str(ks.get('hotkey', 'ctrl+alt+q')).title()}"
            + (" ya da fareyi sol üst köşede bekletmek" if ks.get("corner_trigger") else "") + ".",
            "Başka penceredeyken cevap gelirse bildirim gösterir. Spotlight: ekranda bir bölgeyi işaretleyip gösterir."]


def _guvenlik():
    return ["Onay kutusu: dosya silme, üzerine yazma, kullanıcı klasörü dışına yazma, riskli PowerShell komutları, "
            "değiştiren eklenti araçları ve güvenlik müdahaleleri önce onay ister.",
            "API anahtarları sadece kullanıcının kendi config.yaml dosyasında durur; veriler data/ klasöründe, yerelde.",
            "İnternete çıkanlar (dürüst): her mesaj, ilgili hafıza bağlamı ve araç sonuçları cevap üretilsin diye seçili "
            "modelin sağlayıcısına (Groq, NVIDIA ya da Google Gemini) gönderilir; ekran görüntüsü istenirse Gemini'ye "
            "gider; anlamsal hafıza metinleri embedding için Google'a gider; web aramaları arama servislerine gider. "
            "Gizli sohbet kayıt tutmaz ama mesaj yine modele gider. FENIX'in kendi telemetrisi yoktur.",
            "FENIX geliştiricinin kişisel iletişim bilgilerini paylaşmaz."]


def _sinirlar():
    return ["Sadece Windows.",
            "İnternet gerekir; çevrimdışı yerel model yok (Ollama ile yerel model ileride planlanıyor).",
            "Ücretsiz Groq kotası: dakikalık sınırda bekler, günlük sınır dolunca daha küçük yedek modele geçer; "
            "yoğunlukta yavaşlar ve cevap kalitesi düşebilir.",
            "Adım sınırları: Güvenli/Normal 6, Devil 12 araç adımı; çok uzun işler yarım kalabilir.",
            "Ekranı görür ama ekranda tıklama/yazma (bilgisayar kullanımı) yapamaz.",
            "Kullandığı açık kaynak modeller büyük ticari asistanların modellerinden daha zayıftır; tek geliştiricili "
            "bir projedir."]


_BOLUM_FN = {"kimlik": _kimlik, "modlar": _modlar, "modeller": _modeller, "yetenekler": _yetenekler,
             "hafiza": _hafiza, "eklentiler": _eklentiler, "arayuz": _arayuz, "guvenlik": _guvenlik,
             "sinirlar": _sinirlar}
_BASLIK = {"kimlik": "KİMLİK", "modlar": "MODLAR", "modeller": "MODELLER VE SAĞLAYICILAR",
           "yetenekler": "YETENEKLER (ARAÇLAR)", "hafiza": "HAFIZA", "eklentiler": "EKLENTİLER", "arayuz": "ARAYÜZ",
           "guvenlik": "GÜVENLİK VE GİZLİLİK", "sinirlar": "SINIRLAMALAR"}


def fenix_hakkinda(bolum: str = "hepsi"):
    """FENIX aracı: kendisi hakkındaki gerçek bilgiler (o anki durumdan)."""
    b = (bolum or "hepsi").strip().lower()
    b = {"hafıza": "hafiza", "arayüz": "arayuz", "güvenlik": "guvenlik", "sınırlar": "sinirlar",
         "sınırlamalar": "sinirlar", "gizlilik": "guvenlik"}.get(b, b)
    secilen = list(BOLUMLER) if b in ("", "hepsi", "tumu", "tümü", "all") else [b] if b in _BOLUM_FN else None
    if secilen is None:
        return {"status": "error", "message": "Bölüm adları: hepsi, " + ", ".join(BOLUMLER)}
    parca = []
    for k in secilen:
        try:
            satirlar = _BOLUM_FN[k]()
        except Exception as e:
            fx.report_error("fenix_hakkinda", f"{k}: {e}")
            satirlar = ["(bu bölüm okunamadı)"]
        parca.append(_BASLIK[k] + "\n" + "\n".join("- " + s for s in satirlar))
    return {"status": "ok", "message": "\n\n".join(parca) + "\n\nNOT: Burada olmayan bir özellik hakkında 'emin "
                                                           "değilim' de; uydurma."}


SCHEMA = {"name": "fenix_hakkinda",
          "description": ("FENIX'in KENDİSİ hakkındaki gerçek bilgiler: sürüm, modlar ve modelleri, sağlayıcılar, araçlar, "
                          "hafıza, eklentiler, arayüz pencereleri, güvenlik ve gizlilik (hangi veri internete çıkar), "
                          "sınırlamalar. Kendin, özelliklerin, modların, gizlilik sorulduğunda ya da kendini anlatan bir "
                          "belge istendiğinde ÖNCE bunu çağır ve sadece buradaki bilgileri kullan."),
          "parameters": {"type": "object", "properties": {
              "bolum": {"type": "string", "description": "hepsi (varsayılan) ya da: " + ", ".join(BOLUMLER)}}}}

ARAC_DESENI = (r"kendin|kendini|kendinden|kendine|kendi hakkında|\bfenix|neler yapabil|ne yapabil|yetenek|özellikler|"
               r"modların|modlar|hangi model|gizlilik|verilerim|sınırlamaların|tanıt")


def install(cfg=None):
    """Aracı ekler (uygulama açılırken). cfg: config.yaml içeriği (modlar, modeller, kısayollar buradan okunur)."""
    global CFG
    if cfg is not None:
        CFG = cfg
    if "fenix_hakkinda" in fx.WHITELISTED_FUNCTIONS:
        return
    fx.WHITELISTED_FUNCTIONS["fenix_hakkinda"] = fenix_hakkinda
    fx.READONLY_FUNCTIONS.add("fenix_hakkinda")
    fx.FUNCTION_SCHEMAS.append(SCHEMA)
    try:
        from .llm_client import LLMClient
        LLMClient._TOOL_GROUPS.append((ARAC_DESENI, {"fenix_hakkinda"}))
    except Exception:
        pass
