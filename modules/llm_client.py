# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Çoklu Sağlayıcı LLM Router
--------------------------
- Metin/sohbet: moda göre Groq (hızlı) veya Gemini. Groq anahtarı yoksa Gemini.
- Ekran görme (vision): HER ZAMAN Gemini (Groq metin modelleri görüntü göremez).
- Fonksiyon çağırma: Groq anahtarı varsa Groq üzerinden (Gemini kotası harcanmaz);
  Groq hata verirse Gemini'ye düşülür. Groq yoksa Gemini araçlı akışı kullanılır.

Bu tasarım, kullanıcının mevcut çalışan Gemini kurulumunu bozmadan üstüne
Groq hızını ekler; Groq opsiyoneldir.
"""
import re
import time
import base64
import json

import requests

from . import functions as fx
from . import imza
from . import i18n


class _LazyModule:
    """google.genai ağır bir pakettir: ilk kullanıldığı anda yüklenir (yan sohbet yalnızca Groq ile çalışırsa hiç yüklemez)."""
    def __init__(self, name):
        self._name = name
        self._mod = None

    def __getattr__(self, attr):
        if self._mod is None:
            import importlib
            self._mod = importlib.import_module(self._name)
        return getattr(self._mod, attr)


genai = _LazyModule("google.genai")
types = _LazyModule("google.genai.types")


# Mesaja eklenen zaman damgası ("[Şu an: 2026-10-09 15:55, Cuma]"). Model bunu bazen cevabın başına
# kopyalıyor; sadece makine biçimindeki damga silinir ("Şu an saat 15:55" gibi doğal cümlelere dokunulmaz).
_TIME_STAMP_RE = re.compile(
    r"^[ \t]*[*_]*\[?[ \t]*Şu an[ \t]*:[ \t]*\d{4}-\d{2}-\d{2}[ \t]+\d{1,2}:\d{2}"
    r"(?:[ \t]*,[ \t]*[^\]\n]{0,14})?[ \t]*\]?[*_]*[ \t]*(?:\r?\n)*")


BOZUK_CEVAP = ("Model bu sefer bozuk bir cevap üretti (anlamsız nokta ve yıldız dizisi), o yüzden göstermedim. "
               "Bir daha sorar mısın? Uzun bir belge istiyorsan dosya adını .docx ya da .pdf olarak söylemen yeterli.")


def bozuk_cevap_temizle(text):
    """Model bazen sayfalarca '…', '**', '...' üretip çöküyor (04.11, PDF isteği). Harf oranı çok düşük uzun
    cevaplar ekrana basılmaz; yerine kısa bir açıklama döner."""
    t = text or ""
    if len(t) < 300:
        return t
    harf = sum(ch.isalpha() for ch in t)
    satirlar = [x.strip() for x in t.splitlines() if x.strip()]
    cop = sum(1 for x in satirlar if sum(ch.isalpha() for ch in x) <= 3)
    if harf / len(t) < 0.25 or (len(satirlar) >= 10 and cop / len(satirlar) > 0.6):
        print(f"[GROQ] bozuk cevap atıldı ({len(t)} karakter, harf oranı {harf / len(t):.2f})")
        return BOZUK_CEVAP
    return t


def strip_time_stamp(text):
    """Cevabın başındaki '[Şu an: ...]' damgasını (birden fazla kez yazılmışsa hepsini) temizler."""
    if not isinstance(text, str):
        return text
    prev = None
    while prev != text:
        prev, text = text, _TIME_STAMP_RE.sub("", text, count=1)
    return text


def _identity_block():
    """FENIX'in kendini doğru tanıması için kısa kimlik bilgisi (sürüm, dosyalar, güncelleme yolu)."""
    import os
    from .version import VERSION
    root = os.path.abspath(".")
    return (
        f"KİMLİK: Sen FENIX v{VERSION}'sün: kullanıcının kendi bilgisayarında çalışan, Mustafa Koç'un adım adım "
        "geliştirdiği bir Python masaüstü uygulamasısın (CustomTkinter arayüz). (Geliştirirken kodlama yardımcısı olarak "
        "Claude kullanıldı; sen çalışırken Claude'a, OpenAI'a ya da Anthropic'e BAĞLANMAZSIN.) Bir şirketin bulut "
        "ürünü değilsin; 'OpenAI tarafından güncellenirim', 'kendi dosyam yok' gibi şeyler SÖYLEME. Dil modelleri "
        "senin dışarıdan kullandığın beyinlerdir: sohbet ve araçlar Groq üzerindeki açık kaynak gpt-oss modelleri "
        "(yedek: NVIDIA), ekran görme ve anlamsal hafıza Google Gemini. Model değişse de FENIX aynı uygulamadır.\n"
        "KENDİN: Kendin, modların, özelliklerin, modellerin, gizlilik ya da sınırlamaların sorulduğunda veya kendini "
        "anlatan bir belge istendiğinde ÖNCE fenix_hakkinda aracını çağır ve SADECE oradaki bilgileri kullan. Orada "
        "olmayan bir özellik için 'emin değilim' de; dosya adlarını mod sanma, uydurma özellik/puan ekleme.\n"
        f"DOSYALARIN: proje klasörün {root}. app.py (arayüz); modules/ içinde functions.py (araçlar), "
        "llm_client.py (modeller ve bu talimat), agent.py (görev akışı), memory.py (hafıza), research.py (derin "
        "araştırma), web_analyzer.py (site analizi), pc_tools.py (PC araçları), command_memory.py (komut hafızası), "
        "reminders.py, notifier.py vb.; config.yaml (ayarlar, API "
        "anahtarları); README.md ve docs/ (kurulum rehberleri, sürüm notları); data/ (kalıcı hafıza fenix_memory.db ve chroma_db, raporlar, "
        "hatalar.log, ayarlar). Hafızan KALICIDIR, oturum kapanınca silinmez. Kendi kodun sorulursa read_file ile "
        "bu klasördeki dosyaları okuyabilirsin.\n"
        "GÜNCELLEMELER: Kendiliğinden güncellenmezsin. Kullanıcı yeni sürümü zip olarak alıp proje klasörünün "
        "üzerine açar ya da GitHub'dan çeker (config.yaml ve data/ korunur); neyin değiştiği docs/CHANGELOG.md'de yazar. "
        "FENIX 1.0, JARVIS v6 tabanından çıkmış, çok dilli (TR/EN/DE/RU/FR/ES) kişisel asistan sürümüdür.\n"
        + imza.identity_text() + "\n"
    )


def build_system_instruction(mode_key, mode_cfg):
    base = _identity_block() + (
        "Sen kullanıcının masaüstü asistanısın (FENIX). Kullanıcının seçtiği dilde (aşağıdaki DİL/LANGUAGE "
        "kuralı) doğal ve net konuş. 'efendim/baba' gibi hitaplar kullanma. Cevapların hem ekranda "
        "yazı olarak görünecek hem de sesli okunabilecek.\n\n"
        "SESLENDİRME: Çok dilli bir ses motoru kullanılıyor; İngilizce isim ve "
        "terimleri normal orijinal yazımıyla yaz, fonetik uydurma.\n\n"
        "HAFIZA: Sana '[İlgili geçmiş bağlam]' başlığıyla bu sohbetin son mesajları ve kalıcı hafızandan "
        "(önceki sohbetler/günler ve kullanıcının notları) ilgili kayıtlar verilir; bu senin kalıcı hafızandır. "
        "'oturumlar arası hafızam yok' gibi yanlış bir şey söyleme. '[Eski sohbet: ...]' ve '[Eski mesaj ...]' satırları "
        "önceki sohbetlerden (JARVIS'ten aktarılanlar dahil) bulunan kayıtlardır; geçmiş bir konu sorulursa 'kayıt yok' "
        "demeden önce bunlara bak ve oradaki bilgiyle cevap ver. Orada sadece kullanıcının mesajları varsa bunu belirt.\n\n"
        "HATALAR: Bir araç hata verirse hata metnini ASLA okuma ya da aktarma. Sadece "
        "'Bir hata ile karşılaştım, ayrıntıyı hata notlarına kaydettim.' de ve gerekirse "
        "ne yapılabileceğini kısaca öner. Ayrıntı sistem tarafından kaydedilir.\n\n"
        "WEB: Web sayfası okumak/aramak için ASLA run_command (PowerShell) kullanma; read_webpage ve "
        "search_web araçlarını kullan.\n\n"
        "DOSYA OLUŞTURMA: Kod, HTML/CSS/JS, metin, Word (.docx) ya da PDF gibi bir dosya oluşturmak için HER ZAMAN "
        "write_file kullan (path + content; Word/PDF için content Markdown). UZUN BELGE: önce gereken bilgiyi topla "
        "(araştırma gerekiyorsa en fazla 3-4 arama), sonra belgeyi TEK SEFERDE eksiksiz yaz; yazdıktan sonra yeniden "
        "araştırıp aynı belgeyi tekrar yazma. İstenen bölümlerin hepsini yaz, bilgi yoksa o bölüme 'bilgi bulunamadı' "
        "yaz. run_command ile Set-Content / Out-File / @' ... '@ kullanarak dosyaya içerik yazma. "
        "Site gibi çok dosyalı işlerde her dosya için ayrı write_file çağır (ör. index.html, style.css, script.js). "
        "VAR OLAN bir dosyada küçük bir değişiklik için edit_file kullan, bütün dosyayı yeniden yazma. Büyük dosyada "
        "read_file önce içindekiler listesini verir; ilgili yeri find (ör. 'footer') ya da start_line/end_line ile oku.\n\n"
        "PC KONTROLÜ: Sesi arttırma/azaltma/sessize alma için adjust_volume (kesin seviye için set_system_volume), "
        "parlaklık için set_brightness, Wi-Fi/Bluetooth için set_radio, uygulama kapatmak için close_app (uygulama adı verilmeden "
        "'bunu/şunu/öndekini kapat' denirse close_front_app), müzik/video "
        "kontrolü için media_control, kilit/uyku/ekranı kapatma için power_action, pencereler için window_action, "
        "dosya/klasör silmek için delete_file (Geri Dönüşüm Kutusu'na taşır, onay sorar), kurulu uygulamalar için "
        "list_installed_apps ve scan_pc araçlarını kullan; bunlar için run_command ile PowerShell yazma. 'ses aç' gibi "
        "kısa komutlarda tek araç çağır ve tek kısa cümleyle cevap ver: FENIX başarılı tek-araçlı komutları kendi "
        "komut hafızasına yazar ve bir dahaki sefere yapay zekâya sormadan çalıştırır.\n\n"
        "GÜVENLİK: Tarama sonucunda şüpheli bir şey bulursan önce kullanıcıya sade dille ne bulduğunu ve neden "
        "dikkat çektiğini anlat, 'kesin virüs' deme. stop_process, remove_startup_program, enable_protection gibi "
        "müdahaleleri SADECE kullanıcı açıkça istediğinde çağır; kendiliğinden yapma, teklif et.\n\n"
        "EKRAN: Kullanıcının ekranını görebilirsin: look_at_screen aracını çağır (ya da mesajda '[Ekranın şu "
        "anki görüntüsü]' tarifi gelir). 'Ekranını göremiyorum' DEME; araç hata verirse hatanın söylediği sebebi aktar.\n\n"
        "BİÇİM: Sohbet cevapları sesli okunur; cevapta markdown işaretleri (yıldız, diyez, tire çizgileri) ve TABLO "
        "(| ... |) kullanma, düz yaz (bu kural write_file ile yazılan .docx/.pdf/.md belge İÇERİĞİ için geçerli değil: "
        "belgede # başlık, - madde ve | tablo | kullan); karşılaştırma gerekirse kısa paragraflar ya da numaralı satırlar kullan. "
        "Kaynak/adres listesi vereceksen en sona 'Kaynaklar:' başlığıyla yaz; bu bölüm sesli okunmaz, sadece yazıda kalır.\n\n"
        "GERİ BİLDİRİM: Kullanıcı teşekkür eder ya da önceki cevap hakkında yorum yaparsa yeni bir araştırma "
        "başlatma; kısaca karşılık ver ve isteğini (ör. biçim tercihi) not et.\n\n"
        "BAĞLAM: Konuşmanın akışını takip et. Öznesi olmayan kısa takip sorularını ('maili var mı', 'o ne zaman "
        "çıktı', 'peki fiyatı') bir önceki konuya bağla: 'Seni kim yarattı?' sorusundan sonra gelen 'maili var mı' "
        "yaratıcıyı sorar, seni değil. Gerçekten iki anlama gelebiliyorsa tahmin etme, tek cümleyle sor (ör. "
        "'Mustafa Koç'un mu, benim mi?').\n\n"
        "GERÇEKÇİLİK: Bir fikir, plan ya da istek değerlendirirken önce olabilirliğine bak, tonuna sonra karar ver. "
        "'Harika fikir', 'kesinlikle yapabilirsin', 'mükemmel soru' gibi övgü ve onay cümleleriyle başlama; övgü "
        "ancak somut bir gerekçesi varsa yapılır. Plan, hedef ya da 'bu olur mu' sorulduğunda kısaca: olabilirlik "
        "(yüksek / orta / düşük), en büyük 1-3 engel, gerekenler (zaman, para, beceri) ve ilk somut adım. Olmayacak "
        "ya da çok zor bir şeyse açıkça söyle, nedenini ver, sonra yapılabilir bir alternatif öner. Bildiğinle "
        "tahminini ayır ('kesin', 'muhtemelen', 'emin değilim'). Kullanıcı itiraz ederse yeni bir bilgi ya da "
        "gerekçe sunmadıkça görüşünü değiştirme; sadece ısrar edildi diye 'haklısın' deme. Kullanıcının yanlış "
        "bildiği bir şey varsa nazikçe düzelt. Gerçekçi olmak kaba olmak değildir: sakin ve destekleyici ol, ama "
        "yanıltma.\n\n"
        "ZAMAN: Her mesajın başında '[Şu an: ...]' ile güncel tarih ve saat verilir; tarih/saat hesaplarını "
        "(hatırlatmalar, 'yarın', 'iki saat sonra') buna göre yap. Bu satır sadece senin içindir: cevabına "
        "ASLA '[Şu an: ...]' yazma ya da kopyalama. Kullanıcı saati sorarsa doğal bir cümleyle söyle.\n\n"
        "YETENEKLERİN (zaten var, 'eklenebilir' diye önerme): ekrana bakma ve eklenen/yapıştırılan görselleri "
        "okuma; PDF/Word/Excel/kod dosyalarını okuma; dosya arama/listeleme/okuma/yazma; web arama ve sayfa okuma; "
        "Devil'de derin araştırma ve rapor; uygulama/site/klasör açma, ses seviyesi, PowerShell (riskliler onaylı); "
        "hatırlatma; kendi ses hızı/tonu (set_voice); ses arttır/azalt, parlaklık, Wi-Fi/Bluetooth, uygulama kapatma, medya "
        "tuşları, kilit/uyku, pencere yönetimi, 'bunu kapat' (öndeki pencere), 'ne çalışıyor' ve 'bilgisayar neden yavaş' (pc_awareness), "
        "dosya silme (Geri Dönüşüm Kutusu), kurulu uygulama envanteri; öğrenen "
        "komut hafızası ('Öğrendiklerim'); kısayol komutları; 'not al', 'bunu unut'; ayrı/gizli sohbetler; "
        "Windows güvenlik durumu, şüpheli süreç taraması, başlangıç bekçisi ve onaylı müdahale (süreç sonlandırma, "
        "başlangıçtan kaldırma/geri yükleme, Defender ve güvenlik duvarını açma).\n"
        "Bir istekte birden çok iş varsa (ör. 'VS Code'u ve Spotify'ı aç, sonra proje klasörünü göster') "
        "gerekli araçları sırayla/aynı anda çağırarak hepsini yap."
    )

    if mode_key == "safe":
        base += (
            "\n\nMOD: GÜVENLİ. Sadece okuma, danışma ve sohbet yaparsın (ekrana bakma, web sayfası okuma ve "
            "arama serbest). Hiçbir sistem işlemi (uygulama açma, dosya, komut) YAPAMAZSIN; kullanıcı "
            "böyle bir şey isterse, bunun için Normal veya Devil moda geçmesi "
            "gerektiğini kibarca söyle."
        )
    elif mode_key == "normal":
        base += (
            "\n\nMOD: NORMAL. Gündelik asistan. Uygulama/site/klasör açma, ses "
            "ayarlama gibi güvenli işlemleri yapabilirsin (bunlar otomatik, kısa "
            "bir doğrulama sorusuyla). Silme/komut gibi riskli işlemlerde sistem "
            "otomatik onay kutusu gösterir. Bilgi toplamak için tarayıcı açma, read_webpage / "
            "search_web kullan; open_url yalnızca kullanıcı bir şeyin açılmasını istediğinde."
        )
    elif mode_key == "devil":
        base += (
            "\n\nMOD: DEVIL. Derin analiz ve ajan modu. Web sitesi analizi, çok "
            "adımlı görevler, kod/güvenlik denetimi yaparsın; teknik ve doğrudan "
            "konuş. Yine de dosya silme, sistem komutu çalıştırma veya dışarı veri "
            "gönderme gibi KRİTİK işlemlerde sistem onay kutusu gösterir - bu "
            "senin kontrolünde değildir, kullanıcı onaylamazsa yapılmaz.\n\n"
            "ARAŞTIRMA: Araştırma/analiz/inceleme isteklerinde ASLA tarayıcı sekmesi açma. Önce search_web "
            "(gerekirse) ile kaynakları bul, sonra read_webpage ile en az 3-6 sayfayı arka planda oku, "
            "gerekirse bulduğun linklerden devam et. Sonunda okuduğun kaynakları listeleyerek derli toplu "
            "bir rapor ver. open_url yalnızca kullanıcı 'aç' dediğinde kullanılır."
        )
    elif mode_key == "ogrenme":                 # yalnızca özel sürümde bulunan mod
        try:
            from . import ogrenme
            base += ogrenme.MODE_PROMPT
        except ImportError:
            pass
    return base + "\n\n" + i18n.reply_rule()


class GeminiUnavailable(Exception):
    """Denenen bütün Gemini modelleri/anahtarları kullanılamadı. summary: her model için Türkçe durum."""
    def __init__(self, summary, last=None):
        super().__init__(summary)
        self.summary = summary
        self.last = last


def _retry_seconds(text, default=3600):
    """Google'ın 429 cevabındaki bekleme süresi ('retry in 3h49m27s' ya da retryDelay: '13767s')."""
    m = re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", text)
    if m:
        return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3))
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"](\d+)s", text)
    return float(m.group(1)) if m else default


_TOOL_RESULT_MAX = 6000      # Groq'a geri verilen tek araç sonucunun üst sınırı (karakter)
_OLD_ARG_MAX = 300           # geçmişteki eski araç çağrılarında (ör. write_file içeriği) metin alanı sınırı


def _shrink(obj, max_str):
    """Sözlük/liste içindeki uzun metinleri kısaltır (yapı bozulmaz, JSON geçerli kalır)."""
    if isinstance(obj, str):
        return obj if len(obj) <= max_str else obj[:max_str] + f" …(kısaltıldı, toplam {len(obj)} karakter)"
    if isinstance(obj, dict):
        return {k: _shrink(v, max_str) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_shrink(v, max_str) for v in obj]
    return obj


def tool_result_text(result, limit=_TOOL_RESULT_MAX):
    """Araç sonucunu Groq'a gidecek metne çevirir; büyükse önce uzun alanları, sonra bütünü kısaltır."""
    text = json.dumps(result, ensure_ascii=False)
    if len(text) <= limit:
        return text
    text = json.dumps(_shrink(result, max(400, limit // 2)), ensure_ascii=False)
    if len(text) > limit:
        text = text[:limit] + " …(araç sonucu kısaltıldı)"
    return text


class GroqLimit(Exception):
    """Denenen bütün Groq modellerinin günlük sınırı dolu."""


def _groq_retry_seconds(text, default=3600):
    """Groq'un 429 mesajındaki bekleme süresi ('Please try again in 1h2m3.5s')."""
    m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", text or "")
    if not m:
        return default
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3))


def _groq_reason(e):
    """Groq hatasının kısa Türkçe sebebi (hata notu ve kullanıcı mesajı için)."""
    if isinstance(e, GroqLimit):
        return str(e)
    resp = getattr(e, "response", None)
    code = getattr(resp, "status_code", None)
    body = (getattr(resp, "text", "") or "")[:600].lower()
    if code == 429 or "rate limit" in body:
        if "per day" in body or "tpd" in body or "rpd" in body:
            return "Groq günlük sınırı doldu"
        return "Groq dakikalık sınırına takıldı"
    if code == 413 or "too large" in body:
        return "istek Groq için çok büyük"
    if code in (401, 403):
        return "Groq anahtarı geçersiz ya da yetkisiz"
    if code == 400:
        return "Groq isteği reddetti (biçim/araç hatası)"
    if code and code >= 500:
        return f"Groq sunucusu hata verdi ({code})"
    if isinstance(e, (requests.ConnectionError, requests.Timeout)):
        return "Groq'a ulaşılamadı (bağlantı/zaman aşımı)"
    return f"Groq hatası: {str(e)[:120]}"


class LLMClient:
    def __init__(self, gemini_api_key, groq_api_key="", fallbacks=None, gemini_backup_keys=None,
                 groq_fallbacks=None, lazy_gemini=False):
        self.gemini_api_key = gemini_api_key
        self.fallbacks = list(fallbacks or [])      # kota/404 durumunda sırayla denenecek yedek modeller
        self.groq_api_key = (groq_api_key or "").strip()
        # Groq yedek modelleri: moddaki modelin (ör. gpt-oss-120b) GÜNLÜK sınırı dolunca sırayla denenir.
        # Groq'ta sınırlar model başınadır; 20b'nin ayrı günlük hakkı vardır.
        self.groq_fallbacks = list(groq_fallbacks) if groq_fallbacks is not None else ["openai/gpt-oss-20b"]
        self._groq_cooldown = {}   # model -> (bu zamana kadar atla, bitiş saati metni)
        # Yedek Gemini anahtarları (başka Google hesabı = ayrı kota). Ana anahtarın kotası dolunca sırayla denenir.
        self._gemini_backups = [k.strip() for k in (gemini_backup_keys or []) if isinstance(k, str) and k.strip()
                                and k.strip() != gemini_api_key and "BURAYA" not in k]
        self._gc = None
        if not lazy_gemini:
            self._make_gemini_clients()
        self._cooldown = {}   # (anahtar sırası, model) -> (bu zamana kadar deneme, sebep metni)
        self._chats = {}  # (mode_key, model) -> gemini chat session (araçlı)
        self._groq_hist = {}  # mode_key -> Groq mesaj geçmişi (araçlı sohbet için)
        # Ortak sohbet kaydı (04.11): hangi yoldan (Groq, Gemini/ekran, derin araştırma, komut hafızası) ve hangi
        # modda cevap verilirse verilsin, bir sonraki mesajı cevaplayan yol önceki konuşmayı görür. Önceden ekran
        # cevabı (Gemini) Groq geçmişine girmiyordu, mod değişince de konuşma kayboluyordu.
        self._ortak = []          # [{"id", "user", "assistant", "kaynak"}]
        self._ortak_no = 0
        self._gorulen = {}        # kaynak -> gördüğü son kayıt numarası
        self._son_kaynak = None   # son cevabı üreten yol (kendi geçmişinde zaten var)
        self._recent_tools = {}  # mode_key -> son istekte kullanılan araç adları
        self.last_calls = []     # son ask() sırasında çalışan araçlar: [(ad, argümanlar, sonuç)] (komut hafızası öğrenir)
        fx.set_vision_handler(self.describe_image)

    # --- Gemini istemcileri (lazy_gemini=True ise ilk kullanımda oluşur) ---
    def _make_gemini_clients(self):
        if self._gc is None:
            self._gc = [genai.Client(api_key=self.gemini_api_key)] + [genai.Client(api_key=k) for k in self._gemini_backups]
        return self._gc

    @property
    def gemini_client(self):
        return self._make_gemini_clients()[0]

    @gemini_client.setter
    def gemini_client(self, value):
        self._make_gemini_clients()[0] = value

    @property
    def _gclients(self):
        return self._make_gemini_clients()

    @_gclients.setter
    def _gclients(self, value):
        self._gc = list(value)

    # --- GROQ ortak istek (429'da bekleyip yeniden dener) ---
    def _groq_post(self, payload, timeout=90, max_wait=40, endpoint="groq"):
        """OpenAI uyumlu sohbet isteği. endpoint: "groq" (varsayılan) ya da "nvidia" (build.nvidia.com)."""
        if endpoint == "nvidia":
            from . import nvidia
            url = nvidia.URL
            headers = {"Authorization": f"Bearer {nvidia.CFG['key']}", "Content-Type": "application/json"}
            timeout = max(timeout, nvidia.CFG.get("timeout", 240))     # NVIDIA ücretsiz katmanı yavaş olabilir
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code == 429 and attempt < 3:
                low = (r.text or "")[:600].lower()
                if "per day" in low or "tpd" in low or "rpd" in low:
                    break                        # günlük sınır: beklemek işe yaramaz, hemen sıradaki modele geç
                try:
                    wait = float(r.headers.get("retry-after", 0)) or (2 ** attempt * 3)
                except Exception:
                    wait = 2 ** attempt * 3
                if wait > max_wait:
                    break
                print(f"[GROQ] hız sınırı, {wait:.0f} sn bekleniyor...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
        return r.json()

    def complete(self, mode_cfg, prompt, system=None, fast=False, fast_model=None, temperature=0.4,
                 gemini_fallback=True, extra=None):
        """Araçsız, persona'sız metin üretimi (araştırma motoru için).
        fast=True: hafif/hızlı model (not çıkarma gibi çok sayıda küçük iş). Groq yoksa/başarısızsa Gemini.
        gemini_fallback=False: Gemini'ye ASLA düşme (kotası ekran görme için ayrılmış; komut hafızası gibi arka plan
        işleri Groq olmazsa hata verir)."""
        system = system or "Sen titiz bir araştırma asistanısın. Uydurma bilgi verme."
        system = system + "\n\n" + i18n.reply_rule()
        if self.groq_api_key:
            model = (fast_model or "openai/gpt-oss-20b") if fast else mode_cfg.get("groq_model", "openai/gpt-oss-120b")
            try:
                payload = {"model": model, "temperature": temperature,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": prompt}]}
                if extra:
                    payload.update(extra)        # ör. öğrenme alanı: {"reasoning_effort": "low", "max_tokens": ...}
                data = self._groq_post(payload)
                return data["choices"][0]["message"].get("content") or ""
            except Exception as e:
                if not gemini_fallback and not self._nvidia_models():
                    raise
                print(f"[GROQ UYARI] {e} -> sıradaki sağlayıcı")
        for nm in self._nvidia_models()[:2]:
            try:
                payload = {"model": nm, "temperature": temperature,
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
                data = self._groq_post(payload, endpoint="nvidia")
                return data["choices"][0]["message"].get("content") or ""
            except Exception as e:
                print(f"[NVIDIA UYARI] {nm}: {str(e)[:120]}")
        if not gemini_fallback:
            raise RuntimeError("Groq/NVIDIA kullanılamadı; bu iş Gemini kotasını harcamaz")
        return self._gemini_try(
            self._gemini_models(mode_cfg.get("gemini_model")),
            lambda client, model, ki: client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system, temperature=temperature)).text or "")

    # --- GROQ (metin, hızlı) ---
    def _groq_chat(self, model, system_instruction, user_text, memory_context=""):
        content = user_text
        if memory_context:
            content = f"[İlgili geçmiş bağlam]\n{memory_context}\n\n{user_text}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": content},
            ],
            "temperature": 0.7,
        }
        data = self._groq_post(payload)
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _allowed(mode_cfg):
        """Bu modda modele verilecek araç adları: eylem yetkisi varsa hepsi, yoksa salt okuma araçları."""
        return set(fx.WHITELISTED_FUNCTIONS) if mode_cfg.get("allow_actions") else set(fx.READONLY_FUNCTIONS)

    # Her istekte 20 aracın tamamını göndermek ~2500 token tutuyor; Groq ücretsiz katmanında dakikalık
    # token sınırını hızla dolduruyordu. İsteğe göre ilgili araç grupları seçilir.
    _CORE_TOOLS = {"open_app_by_name", "open_url", "open_folder_by_name", "run_command", "search_web",
                   "look_at_screen", "write_file"}
    _TOOL_GROUPS = [
        (r"dosya|klasör|klasor|kod|ödev|odev|proje|\.py|\.js|\.ts|\.md|\.txt|\.docx|\.pdf|\.html?|\.css|\.json|"
         r"oku|kaydet|yaz|masaüstü|masaustu|belge|indirilen|listele|bul|html|css|footer|header|düzelt|duzelt|"
         r"kaldır|kaldir|değiştir|degistir|sayfa|site", {"find_files", "list_folder", "read_file", "write_file",
                                                          "edit_file"}),
        (r"hatırlat|hatirlat|alarm|hatırlatma|ertele", {"set_reminder", "list_reminders", "cancel_reminder"}),
        (r"konuş|konus|sesin|sesini|hızlı|hizli|yavaş|yavas|ince|kalın|kalin|ton|ses ayar|yüksek sesle|kısık",
         {"set_voice", "set_system_volume"}),
        (r"ses\b|sesi|%|yüzde|volume|sessiz|sustur|kıs\b|kis\b|arttır|arttir|azalt", {"set_system_volume", "adjust_volume"}),
        (r"parlak|aydınlat|aydinlat|karart|ekran ışığı|ekran isigi|brightness", {"set_brightness"}),
        (r"wi-?fi|kablosuz|bluetooth|blutut|\bbt\b", {"set_radio"}),
        (r"\bsil\b|silme|sildir|silebilir|sil\b|çöp|cop kutusu|geri dönüşüm|geri donusum", {"delete_file", "find_files"}),
        (r"kapat|kapa\b|sonlandır|sonlandir|çık\b|cik\b", {"close_app", "stop_process", "close_front_app"}),
        (r"ne çalışıyor|ne calisiyor|neler çalışıyor|neler calisiyor|ne açık|ne acik|neler açık|neler acik|"
         r"hangi (?:uygulama|program)\w* (?:açık|acik|çalışıyor|calisiyor)|açık (?:uygulama|program)|acik (?:uygulama|program)|"
         r"yavaşla|yavasla|kasıyor|kasiyor|kasma|donuyor|donma|neden yavaş|neden yavas|yavaş çalış|yavas calis",
         {"pc_awareness"}),
        (r"müzik|muzik|şarkı|sarki|parça|parca|oynat|duraklat|durdur|sonraki|önceki|onceki|medya|devam et",
         {"media_control"}),
        (r"kilitle|uyku|uyut|ekranı kapat|ekrani kapat|monitörü kapat|monitoru kapat", {"power_action"}),
        (r"pencere|simge durumu|küçült|kucult|büyüt|buyut|masaüstünü göster|masaustunu goster|öne getir|one getir",
         {"window_action"}),
        (r"kurulu|yüklü|yuklu|uygulamalar|programlar|hangi uygulama|bilgisayarı tara|bilgisayari tara|envanter",
         {"list_installed_apps", "scan_pc"}),
        (r"kısayol|kisayol|rutin|dediğimde|dedigimde|komutları birleştir|modu", {"save_shortcut", "list_shortcuts",
                                                                                 "delete_shortcut"}),
        (r"unut|hafızandan|hafizandan", {"forget"}),
        (r"site|web|internet|http|\.com|\.org|\.net|araştır|arastir|haber|sayfa", {"search_web", "read_webpage",
                                                                                 "open_url", "inspect_website_security"}),
        (r"güvenlik|guvenlik|sertifika|ssl|tls|whois|dns|zafiyet|açık var mı|acik var mi|denetle|denetim",
         {"inspect_website_security"}),
        (r"yayınla|yayinla|yayına çık|yayina cik|github'a|githuba|projemde açık|projemde acik|"
         r"env dosya|gitignore|proje güvenlik|proje guvenlik", {"check_project_security"}),
        (r"bilgisayar|sistem|performans|cpu|işlemci|islemci|ram|bellek|süreç|surec|process|başlangıç program|"
         r"baslangic program|açık port|acik port|disk\b|depolama", {"inspect_system"}),
        (r"\bword\b|\bpdf\b|docx|dışa aktar|disa aktar|indir(?:ebilir)?\s*miyim", {"export_report"}),
        (r"defender|antivirüs|antivirus|güvenlik duvar|guvenlik duvar|firewall|\buac\b|smartscreen|"
         r"windows güvenlik|windows guvenlik|koruma|güvenliği nasıl|guvenligi nasil|bilgisayarım güvenli|"
         r"bilgisayarim guvenli|windows update|windows güncelleme|windows guncelleme",
         {"check_windows_security", "enable_protection"}),
        (r"başlangıç|baslangic|açılışta|acilista|otomatik başla|otomatik basla|otomatik açıl|otomatik acil|"
         r"ben kurdum|ben ekledim|ben yükledim|ben yukledim",
         {"watch_startup_programs", "remove_startup_program", "restore_startup_program"}),
        (r"şüpheli|supheli|zararlı|zararli|virüs|virus|malware|trojan|truva|casus|kötü amaçlı|kotu amacli|"
         r"hacklen|hacklendim|sonlandır|sonlandir|süreci kapat|sureci kapat|\bpid\b|görev yönetici|gorev yonetici",
         {"find_suspicious_processes", "stop_process", "inspect_system"}),
        (r"bağlantı(?:lar)?(?:ı|ları)? göster|baglanti(?:lar)?(?:i|lari)? goster|hangi program.{0,30}(?:bağlı|bagli|bağlan|baglan|ağa|internete|çıkıyor|cikiyor)|"
         r"internete.{0,25}(?:bağlı|bagli|bağlan|baglan)|giden bağlantı|giden baglanti|ağ bağlantı|ag baglanti|\bağ\b|\bag\b",
         {"network_connections"}),
        (r"oltalama|phishing|sahte (?:site|link)|bu link|linki|bağlantı güvenli|baglanti guvenli|güvenli mi|guvenli mi|"
         r"https?://|www\.", {"check_link"}),
        (r"çerez|cerez|cookie|oturum çal|oturum cal|hesab[ıi]m çal|hesab[ıi]m cal|hesap güvenli|hesap guvenli|"
         r"eklenti|hesaplarım ele|hesaplarim ele", {"cookie_guard"}),
        (r"secret|api anahtar|açıkta anahtar|acikta anahtar|klasörü tara|klasoru tara|projeyi tara|projemi tara",
         {"scan_project"}),
    ]

    def _select_tools(self, mode_key, mode_cfg, text):
        """Mesaja göre gönderilecek araç adları (+ bu sohbette son kullanılan araçlar, 'evet yap' gibi devamlar için)."""
        t = (text or "").lower()
        names = set(self._CORE_TOOLS)
        for pat, group in self._TOOL_GROUPS:
            if re.search(pat, t):
                names |= group
        names |= self._recent_tools.get(mode_key, set())
        names |= set(getattr(self, "_extra_tools", None) or ())     # yol hafızasının önerdiği araçlar
        return names & self._allowed(mode_cfg)

    def _groq_tools(self, mode_cfg=None, only=None):
        allowed = self._allowed(mode_cfg or {"allow_actions": True})
        if only is not None:
            allowed = allowed & set(only)
        return [{"type": "function", "function": {
                    "name": sc["name"], "description": sc["description"], "parameters": sc["parameters"]}}
                for sc in fx.FUNCTION_SCHEMAS if sc["name"] in allowed]

    def describe_image(self, question, b64, mode_cfg=None, source="screen"):
        """Görüntüyü Gemini'ye tarif ettirir; yedek modelleri de dener.
        source='screen': canlı ekran görüntüsü, 'image': kullanıcının eklediği/yapıştırdığı görsel."""
        head = ("Bu, kullanıcının bilgisayar ekranının şu anki görüntüsü." if source == "screen" else
                "Bu, kullanıcının eklediği bir görsel (çoğunlukla ekran görüntüsü).")
        prompt = (head + " İçinde ne olduğunu Türkçe, doğru ve ayrıntılı tarif et: hangi uygulama/pencere/sayfa, "
                  "okunabilen bütün önemli yazılar, varsa hata mesajlarının tam metni, kod, tablo ve sayılar. "
                  "Görmediğin şeyi uydurma."
                  + (f"\nKullanıcı özellikle şunu soruyor: {question}" if question else ""))
        img = base64.b64decode(b64)
        try:
            return self._gemini_describe(prompt, img, mode_cfg)
        except Exception as e:                       # v6.0: Gemini'nin hepsi başarısızsa EN SON NVIDIA görsel modeli
            from . import nvidia
            if not nvidia.enabled():
                raise
            try:
                out = nvidia.describe_image(prompt, b64)
                fx._notify("Görsel NVIDIA yedek modeliyle yorumlandı")
                return out
            except Exception as ne:
                fx.report_error("görüntü (NVIDIA yedek)", str(ne)[:300])
                raise e

    def _gemini_describe(self, prompt, img, mode_cfg):
        return self._gemini_try(
            self._gemini_models((mode_cfg or {}).get("gemini_model"), extra=("gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash")),
            lambda client, model, ki: client.models.generate_content(
                model=model, contents=[types.Part.from_bytes(data=img, mime_type="image/jpeg"),
                                       types.Part.from_text(text=prompt)]).text or "(boş tarif)",
            what="görüntü modeli")

    _KESIF_ARACLARI = {"search_web", "read_webpage", "find_files", "list_folder", "read_file", "open_url",
                       "inspect_website_security", "look_at_screen", "open_folder_by_name"}

    @staticmethod
    def _trim_hist(hist, max_msgs=14, max_chars=2500, last_max=None):
        """Gönderilecek geçmiş: son max_msgs mesaj, bir KULLANICI mesajıyla başlar (yoksa araç yanıtı
        çağrısından kopuk kalır ve Groq 400 verir); eski uzun içerikler kısaltılır, son mesaj olduğu gibi."""
        part = hist[-max_msgs:]
        while part and part[0].get("role") != "user":
            part = part[1:]
        if not part:
            # Uzun araç zinciri (7+ tur): pencerede kullanıcı mesajı kalmadı. Görevi unutmasın diye son
            # kullanıcı mesajı başa konur, ardından araç çağrısıyla başlayan son turlar gelir.
            son_u = max((i for i, m in enumerate(hist) if m.get("role") == "user"), default=None)
            kuyruk = hist[-(max_msgs - 1):] if max_msgs > 1 else []
            while kuyruk and kuyruk[0].get("role") != "assistant":
                kuyruk = kuyruk[1:]
            part = ([hist[son_u]] if son_u is not None else []) + kuyruk or hist[-1:]
        out = []
        for i, m in enumerate(part):
            c = m.get("content") or ""
            is_last = i == len(part) - 1
            cap = last_max if is_last else max_chars
            if cap and isinstance(c, str) and len(c) > cap:
                m = dict(m, content=c[:cap] + " …(kısaltıldı)")
            if m.get("tool_calls") and not is_last:
                # Eski araç çağrılarındaki büyük argümanlar (ör. write_file ile yazılan bütün site) her istekte
                # yeniden gönderilip Groq'un dakikalık sınırını dolduruyordu: uzun alanlar kısaltılır.
                calls = []
                for tc in m["tool_calls"]:
                    if not isinstance(tc, dict):
                        calls.append(tc)
                        continue
                    fn = dict(tc.get("function") or {})
                    raw = fn.get("arguments") or ""
                    if len(raw) > _OLD_ARG_MAX * 2:
                        try:
                            fn["arguments"] = json.dumps(_shrink(json.loads(raw), _OLD_ARG_MAX), ensure_ascii=False)
                        except Exception:
                            fn["arguments"] = json.dumps({"not": "uzun argüman kısaltıldı"}, ensure_ascii=False)
                    calls.append(dict(tc, function=fn))
                m = dict(m, tool_calls=calls)
            out.append(m)
        return out

    def _groq_agent_chat(self, mode_key, mode_cfg, user_text, memory_context=""):
        out = self._groq_agent_chat_ic(mode_key, mode_cfg, user_text, memory_context)
        self._son_kaynak = ("groq", mode_key)          # bu konuşma artık bu modun geçmişinde
        return out

    def _groq_agent_chat_ic(self, mode_key, mode_cfg, user_text, memory_context=""):
        """Groq üzerinden araç çağırmalı sohbet (OpenAI uyumlu function calling).
        Mesaj geçmişi mod başına tutulur; araç sonuçları modele geri verilir."""
        hist = self._groq_hist.setdefault(mode_key, [])
        # Geçmişe yalnızca kullanıcının asıl mesajı yazılır. Hafıza bağlamı sadece o anki mesaja eklenir;
        # önceden bağlam her mesajın başına yazılıyordu ve geçmiş kısaltılırken eski SORULAR kesilip atılıyordu
        # (ör. "Seni kim yarattı?" kayboluyor, ardından gelen "Maili var mı?" yanlış anlaşılıyordu).
        kaynak = ("groq", mode_key)
        for e in self._ortak_eksik(kaynak):              # başka yoldan/moddan yapılan konuşmalar
            hist.append({"role": "user", "content": e["user"]})
            hist.append({"role": "assistant", "content": self._kisalt(e["assistant"])})
        content = user_text
        hist.append({"role": "user", "content": content})

        def with_ctx(msgs):
            if not memory_context:
                return msgs
            out = list(msgs)
            for i in range(len(out) - 1, -1, -1):      # son kullanıcı mesajı = bu turun mesajı
                if out[i].get("role") == "user":
                    out[i] = dict(out[i], content=f"[İlgili geçmiş bağlam]\n{memory_context}\n\n"
                                                  f"[Kullanıcının şu anki mesajı]\n{out[i].get('content') or ''}")
                    break
            return out
        selected = self._select_tools(mode_key, mode_cfg, user_text)
        tools = self._groq_tools(mode_cfg, only=selected)
        used = set()
        system = {"role": "system", "content": build_system_instruction(mode_key, mode_cfg)}
        ep = mode_cfg.get("_endpoint", "groq")
        try:
            tur = getattr(self, "tur_siniri", None) or (12 if mode_key == "devil" else 8 if mode_key == "ogrenme" else 6)
            for tur_no in range(tur):   # araç turu sınırı (Devil: derin araştırma)
                payload = {"model": mode_cfg["groq_model"], "messages": [system] + with_ctx(self._trim_hist(hist)),
                           "temperature": 0.6}
                kalan = tur - tur_no
                if used and kalan <= 2:
                    # 04.11: belge isteğinde 6 turun hepsi aramaya gitti, dosya hiç yazılmadı. Son turlarda model
                    # uyarılır: yeni araştırma yok, eldekiyle işi bitir.
                    payload["messages"].append({"role": "system", "content": (
                        f"UYARI: Araç turu hakkının sonundasın (kalan {kalan}). Yeni arama ya da keşif yapma. "
                        "Topladığın bilgiyle işi ŞİMDİ bitir: dosya/belge istendiyse hemen yaz (eksik kalan yerlere "
                        "'araştırılamadı' yaz), değilse cevabı ver.")})
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
                    if used and kalan <= 2:
                        # Uyarı yetmeyebiliyor (04.11, ikinci deneme: yine 6 arama). Son iki turda arama/keşif
                        # araçları hiç verilmez: model ya yazar ya cevap verir.
                        son_araclar = [t for t in tools if t.get("function", {}).get("name") not in self._KESIF_ARACLARI]
                        if son_araclar:
                            payload["tools"] = son_araclar
                        else:
                            payload.pop("tools", None)
                            payload.pop("tool_choice", None)
                try:
                    msg = self._groq_post(payload, endpoint=ep)["choices"][0]["message"]
                except requests.HTTPError as he:
                    code = getattr(he.response, "status_code", 0)
                    body = getattr(he.response, "text", "")[:300]
                    if code in (413, 429) or "too large" in body.lower() or "tokens" in body.lower():
                        # İstek çok büyük / dakikalık token sınırı: kısa geçmiş ve yalnızca temel araçlarla bir kez daha
                        print(f"[GROQ] istek büyük/sınırda ({code}), küçültülüp yeniden deneniyor")
                        payload["messages"] = [system] + self._trim_hist(hist, max_msgs=6, max_chars=800,
                                                                         last_max=2500)
                        if tools:
                            payload["tools"] = self._groq_tools(mode_cfg, only=selected & (self._CORE_TOOLS | used))
                        msg = self._groq_post(payload, max_wait=60, endpoint=ep)["choices"][0]["message"]
                    elif code == 400 and ("should have a name" in body or "harmony" in body.lower()) and len(hist) > 1:
                        # Geçmişteki bozuk bir mesaj şablonu bozuyor: sadece son kullanıcı mesajıyla bir kez daha dene
                        print("[GROQ] şablon hatası, geçmiş temizlenip yeniden deneniyor")
                        del hist[:-1]
                        used.clear()
                        payload["messages"] = [system] + with_ctx(self._trim_hist(hist))
                        msg = self._groq_post(payload, endpoint=ep)["choices"][0]["message"]
                    else:
                        fx.report_error("NVIDIA" if ep == "nvidia" else "Groq", f"{code}: {body}")
                        raise
                raw_calls = msg.get("tool_calls") or []
                # Model bazen adı boş/bozuk bir araç çağrısı üretir; geçmişe girerse Groq sonraki her istekte
                # 400 "Tools should have a name!" verir. Bozuk çağrılar atılır.
                calls = [c for c in raw_calls if isinstance(c, dict) and c.get("id")
                         and isinstance(c.get("function"), dict)
                         and isinstance(c["function"].get("name"), str) and c["function"]["name"].strip()]
                if raw_calls and not calls:
                    print("[GROQ] adı olmayan araç çağrısı atıldı")
                    if not (msg.get("content") or "").strip():
                        return "İsteği bir araca çeviremedim, bir daha dener misin?"
                entry = {"role": "assistant", "content": strip_time_stamp(msg.get("content") or "")}
                if calls:
                    entry["tool_calls"] = calls
                hist.append(entry)
                if not calls:
                    if not used:
                        self._recent_tools.pop(mode_key, None)
                    return bozuk_cevap_temizle(strip_time_stamp(msg.get("content") or "")) or "Tamamlandı."
                for call in calls:
                    name = call["function"]["name"]
                    used.add(name)
                    self._recent_tools[mode_key] = set(used)
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except Exception:
                        args = {}
                    verilen = {t.get("function", {}).get("name") for t in payload.get("tools") or []}
                    if name not in fx.WHITELISTED_FUNCTIONS or name not in self._allowed(mode_cfg):
                        result = {"status": "error", "message": "Bu işlem bu modda yapılamaz."}
                    elif payload.get("tools") is not None and name not in verilen and kalan <= 2:
                        result = {"status": "error", "message": "Arama hakkın bitti; topladığın bilgiyle işi bitir."}
                    else:
                        try:
                            result = fx.WHITELISTED_FUNCTIONS[name](**args)
                        except Exception as e:
                            fx.report_error(name, e)
                            result = {"status": "error", "message": fx.GENERIC_ERROR}
                    self.last_calls.append((name, args, result))
                    hist.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": tool_result_text(result)})
            # Tur hakkı bitti: araçsız son bir istekle model yaptığını özetler (son turda dosya yazılmış olabilir).
            try:
                payload = {"model": mode_cfg["groq_model"], "temperature": 0.4,
                           "messages": [system] + with_ctx(self._trim_hist(hist, max_msgs=8, max_chars=800,
                                                                           last_max=2500)) + [{"role": "system", "content": (
                               "Araç hakkın bitti. Araç çağırma. Kullanıcıya kısaca ne yaptığını, neyin tamamlandığını "
                               "ve neyin yarım kaldığını söyle.")}]}
                ozet = (self._groq_post(payload, endpoint=ep)["choices"][0]["message"].get("content") or "").strip()
                if ozet:
                    hist.append({"role": "assistant", "content": strip_time_stamp(ozet)})
                    return bozuk_cevap_temizle(strip_time_stamp(ozet)) + "\n\n(Adım sınırına ulaşıldı.)"
            except Exception as e:
                print(f"[GROQ] son özet alınamadı: {e}")
            from collections import Counter
            sayim = Counter(n for n, _, _ in self.last_calls)
            ozet = ", ".join(f"{k} ×{v}" for k, v in sayim.most_common()) or "yok"
            yazildi = any(n in ("write_file", "edit_file") and isinstance(r, dict) and r.get("status") == "ok"
                          for n, _, r in self.last_calls)
            return (f"Adım sınırına ulaştım ({tur} adım). Kullandığım araçlar: {ozet}. "
                    + ("Dosya yazıldı." if yazildi else "Dosya/belge yazılamadı.")
                    + (" Daha uzun işler için Devil modunu dene." if mode_key != "devil" else "")
                    + "\n\n(Adım sınırına ulaşıldı.)")
        except Exception:
            # Yarım kalmış tur geçmişi bozmasın: son kullanıcı mesajından itibaren temizle
            while hist and not (hist[-1].get("role") == "user" and hist[-1].get("content") == content):
                hist.pop()
            if hist:
                hist.pop()
            raise

    # --- GEMINI (araçlı + vision) ---
    @staticmethod
    def _is_model_problem(e):
        t = str(e)
        return any(k in t for k in ("429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND", "503", "UNAVAILABLE"))

    def _gemini_models(self, first=None, extra=()):
        out = []
        for m in [first] + self.fallbacks + list(extra):
            if m and m not in out:
                out.append(m)
        return out

    def _gemini_try(self, models, call, what="model"):
        """call(client, model, key_index) her anahtar × model için denenir.
        - Kota dolu (429): o model, Google'ın verdiği süre boyunca atlanır (boşuna istek harcanmaz).
        - Yoğun (503): 3 sn bekleyip aynı model bir kez daha denenir; yine olmazsa 1 dk atlanır.
        - Bulunamadı (404): 1 saat atlanır.
        Hiçbiri olmazsa GeminiUnavailable: her model için ayrı Türkçe durum özetiyle."""
        import datetime as _dt
        notes, last = [], None
        multi = len(self._gclients) > 1
        # Sıra: her model için önce ana, sonra yedek anahtar (daha iyi model, hangi anahtarda olursa olsun önce gelir)
        for model in models:
            for ki, client in enumerate(self._gclients):
                tag = (" (yedek anahtar)" if ki else " (ana anahtar)") if multi else ""
                key = (ki, model)
                until, why = self._cooldown.get(key, (0, ""))
                if until > time.time():
                    notes.append(f"{model}{tag}: {why}")
                    continue
                for attempt in (1, 2):
                    try:
                        return call(client, model, ki)
                    except Exception as e:
                        last = e
                        if not self._is_model_problem(e):
                            raise
                        t = str(e)
                        fx.report_error(what, f"{model}{tag}: {t[:400]}")
                        if "503" in t or "UNAVAILABLE" in t:
                            if attempt == 1:
                                time.sleep(3)
                                continue
                            why = "şu an çok yoğun (geçici), biraz sonra tekrar dene"
                            self._cooldown[key] = (time.time() + 60, why)
                        elif "429" in t or "RESOURCE_EXHAUSTED" in t:
                            secs = _retry_seconds(t)
                            when = _dt.datetime.now() + _dt.timedelta(seconds=secs)
                            kind = "günlük kotası doldu" if secs > 300 else "dakikalık sınıra takıldı"
                            why = f"{kind}, {when:%H:%M}'de yenilenir"
                            self._cooldown[key] = (time.time() + secs, why)
                        else:
                            why = "bu model bulunamadı (config.yaml'daki model adını kontrol et)"
                            self._cooldown[key] = (time.time() + 3600, why)
                        notes.append(f"{model}{tag}: {why}")
                        print(f"[GEMINI UYARI] {notes[-1]}")
                        break
        raise GeminiUnavailable("; ".join(notes) or str(last), last)

    def _gemini_chat(self, mode_key, mode_cfg, user_text, screenshot_b64=None, memory_context=""):
        """Önce moddaki modeli dener; kota (429) / bulunamadı (404) / yoğunluk (503) olursa yedek modellere geçer."""
        return self._gemini_try(
            self._gemini_models(mode_cfg["gemini_model"]),
            lambda client, model, ki: self._gemini_chat_with(model, mode_key, mode_cfg, user_text, screenshot_b64,
                                                             memory_context, client=client, key_index=ki))

    def _gemini_chat_with(self, model, mode_key, mode_cfg, user_text, screenshot_b64=None, memory_context="",
                          client=None, key_index=0):
        client = client or self.gemini_client
        session_key = (mode_key, model, key_index)
        if session_key not in self._chats:
            allowed = self._allowed(mode_cfg)
            function_declarations = [types.FunctionDeclaration(**s) for s in fx.FUNCTION_SCHEMAS if s["name"] in allowed]
            tools = [types.Tool(function_declarations=function_declarations)] if function_declarations else None
            self._chats[session_key] = client.chats.create(
                model=model,
                config=types.GenerateContentConfig(
                    tools=tools,
                    system_instruction=build_system_instruction(mode_key, mode_cfg),
                ),
            )
        chat = self._chats[session_key]

        parts = []
        kaynak = ("gemini",) + tuple(session_key)
        eksik = self._ortak_eksik(kaynak)
        if eksik:                                    # ör. Groq'la yapılan son konuşmalar (ekran isteğinden önce)
            parts.append(types.Part.from_text(text="[Son konuşma — bunlar seninle yapıldı, devamı soruluyor olabilir]\n"
                         + "\n".join(f"Kullanıcı: {e['user']}\nFENIX: {self._kisalt(e['assistant'])}" for e in eksik)))
        if memory_context:
            parts.append(types.Part.from_text(text=f"[İlgili geçmiş bağlam]\n{memory_context}\n"))
        parts.append(types.Part.from_text(text=user_text))
        # screenshot_b64: tek görüntü (str) ya da birden çok görüntü (liste: ekli resimler)
        for img in ([screenshot_b64] if isinstance(screenshot_b64, str) else (screenshot_b64 or [])):
            parts.append(types.Part.from_bytes(data=base64.b64decode(img), mime_type="image/jpeg"))

        response = chat.send_message(parts)
        out = self._handle_gemini_response(chat, response, mode_cfg)
        self._son_kaynak = kaynak
        return out

    def _handle_gemini_response(self, chat, response, mode_cfg):
        fcs = getattr(response, "function_calls", None)
        if fcs:
            parts = []
            for fc in fcs:                      # tek cevapta birden çok iş istenmiş olabilir
                name = fc.name
                args = dict(fc.args) if fc.args else {}
                if name not in fx.WHITELISTED_FUNCTIONS or name not in self._allowed(mode_cfg):
                    result = {"status": "error", "message": "Bu işlem bu modda yapılamaz."}
                else:
                    try:
                        result = fx.WHITELISTED_FUNCTIONS[name](**args)
                    except Exception as e:
                        fx.report_error(name, e)
                        result = {"status": "error", "message": fx.GENERIC_ERROR}
                self.last_calls.append((name, args, result))
                parts.append(types.Part.from_function_response(name=name, response={"result": result}))
            follow = chat.send_message(parts)
            return self._handle_gemini_response(chat, follow, mode_cfg)
        return response.text

    ORTAK_MAX = 40
    ORTAK_CEVAP_MAX = 3000

    def ortak_kaydet(self, user_text, reply, kaynak=None):
        """Tamamlanan bir konuşmayı ortak kayda yazar. kaynak: cevabı üreten yol (onun geçmişinde zaten var)."""
        u, a = (user_text or "").strip(), (reply or "").strip()
        if not (u and a):
            return
        self._ortak_no += 1
        self._ortak.append({"id": self._ortak_no, "user": u, "assistant": a, "kaynak": kaynak})
        del self._ortak[:-self.ORTAK_MAX]
        if kaynak is not None:
            self._gorulen[kaynak] = self._ortak_no

    def _ortak_eksik(self, kaynak, en_fazla=6):
        """Bu yolun henüz görmediği (başka yoldan/moddan yapılmış) son konuşmalar; görüldü olarak işaretler."""
        son = self._gorulen.get(kaynak, 0)
        eksik = [e for e in self._ortak if e["id"] > son and e["kaynak"] != kaynak]
        if self._ortak:
            self._gorulen[kaynak] = self._ortak[-1]["id"]
        return eksik[-en_fazla:]

    def _kisalt(self, t):
        return t if len(t) <= self.ORTAK_CEVAP_MAX else t[:self.ORTAK_CEVAP_MAX] + " …(kısaltıldı)"

    def remember_exchange(self, mode_key, user_text, reply):
        """Yapay zekâya sormadan (komut hafızasıyla) yapılan bir komutu sohbet geçmişine yazar; sonraki mesajlarda
        ('biraz daha', 'geri al') bağlam eksik kalmasın."""
        hist = self._groq_hist.setdefault(mode_key, [])
        hist.append({"role": "user", "content": user_text})
        hist.append({"role": "assistant", "content": reply})
        del hist[:-40]
        self._son_kaynak = ("groq", mode_key)

    def compact_last_user(self, mode_key, short_text):
        """Ekli dosya içeriği sohbet geçmişinde kalıp sonraki her istekte tekrar gönderilmesin
        (Groq hız/boyut sınırı): son kullanıcı mesajını kısa haliyle değiştirir."""
        hist = self._groq_hist.get(mode_key) or []
        for m in reversed(hist):
            if m.get("role") == "user":
                m["content"] = short_text
                break

    def reset_mode_session(self, mode_key=None, ortak_koru=False):
        """ortak_koru=True (mod değişimi): model oturumları sıfırlanır ama konuşma korunur; yeni mod, ortak
        kayıttaki son konuşmaları görür. Yeni sohbet/sohbet açma: her şey sıfırlanır."""
        if ortak_koru:
            self._chats.clear()
            self._groq_hist.clear()
            self._recent_tools.clear()
            self._gorulen.clear()
            return
        if mode_key:
            self._groq_hist.pop(mode_key, None)
            self._recent_tools.pop(mode_key, None)
            for k in [k for k in self._chats if k[0] == mode_key]:
                self._chats.pop(k, None)
        else:
            self._chats.clear()
            self._groq_hist.clear()
            self._recent_tools.clear()
            self._ortak.clear()
            self._gorulen.clear()

    # --- ANA GİRİŞ ---
    def ask(self, mode_key, mode_cfg, user_text, screenshot_b64=None, memory_context=""):
        """
        Yönlendirme mantığı:
        - Ekran görüntüsü varsa VEYA mod eylem yapabiliyorsa -> Gemini (vision+araç)
        - Aksi halde Groq yapılandırılmışsa -> Groq (hızlı metin)
        - Groq yoksa -> Gemini
        """
        import datetime as _dt
        self.last_calls = []
        _days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        _now = _dt.datetime.now()
        user_text = f"[Şu an: {_now:%Y-%m-%d %H:%M}, {_days[_now.weekday()]}]\n{user_text}"
        use_gemini = bool(screenshot_b64)          # yalnızca ekran görme Gemini ister
        provider = mode_cfg.get("provider", "gemini")

        if provider in ("groq", "nvidia") and not use_gemini and (self.groq_api_key or self._nvidia_models()):
            try:
                return strip_time_stamp(self._fast_chain(mode_key, mode_cfg, user_text, memory_context))
            except Exception as e:
                return strip_time_stamp(self._gemini_after_groq(
                    e, lambda: self._gemini_chat(mode_key, mode_cfg, user_text, screenshot_b64, memory_context)))

        return strip_time_stamp(self._gemini_chat(mode_key, mode_cfg, user_text, screenshot_b64, memory_context))

    @staticmethod
    def _nvidia_models():
        try:
            from . import nvidia
            return nvidia.chat_models()
        except Exception:
            return []

    def _provider_order(self, mode_cfg):
        """Hızlı sağlayıcı sırası: moddaki provider önce; diğeri yedek. Gemini en sonda (ask içinde)."""
        order = ["nvidia", "groq"] if mode_cfg.get("provider") == "nvidia" else ["groq", "nvidia"]
        return [p for p in order if (p == "groq" and self.groq_api_key) or (p == "nvidia" and self._nvidia_models())]

    def _nvidia_with_fallback(self, mode_key, mode_cfg, user_text, memory_context=""):
        """NVIDIA modellerini sırayla dener (OpenAI uyumlu, araç çağırmalı)."""
        last = None
        for nm in self._nvidia_models():
            try:
                out = self._groq_agent_chat(mode_key, dict(mode_cfg, groq_model=nm, _endpoint="nvidia"),
                                            user_text, memory_context)
                fx._notify(f"NVIDIA modeli kullanıldı: {nm}")
                return out
            except Exception as e:
                last = e
                fx.report_error("NVIDIA", f"{nm}: {str(e)[:200]}")
        raise last or RuntimeError("NVIDIA modeli yok")

    def _fast_chain(self, mode_key, mode_cfg, user_text, memory_context=""):
        """Groq ve NVIDIA'yı sırayla dener; ikisi de olmazsa son hatayı yükseltir (ask -> Gemini)."""
        last = None
        for p in self._provider_order(mode_cfg):
            try:
                if p == "groq":
                    return self._groq_with_fallback(mode_key, mode_cfg, user_text, memory_context)
                return self._nvidia_with_fallback(mode_key, mode_cfg, user_text, memory_context)
            except Exception as e:
                last = e
                print(f"[{p.upper()} UYARI] {str(e)[:120]} -> sıradaki sağlayıcı")
        raise last or RuntimeError("hızlı sağlayıcı yok")

    def _groq_with_fallback(self, mode_key, mode_cfg, user_text, memory_context=""):
        """Moddaki Groq modeli, günlük sınırı dolarsa yedek Groq modelleri (ör. gpt-oss-20b). Günlük sınırı dolan
        model Groq'un söylediği süre boyunca atlanır. Başka tür hatalar (bağlantı, istek büyük vb.) aynen yükselir."""
        import datetime as _dt
        first = mode_cfg.get("groq_model")
        fallbacks = getattr(self, "groq_fallbacks", ["openai/gpt-oss-20b"])
        cooldown = self.__dict__.setdefault("_groq_cooldown", {})
        models = [m for m in [first] + [x for x in fallbacks if x != first] if m]
        notes = []
        for gm in models:
            until, when = cooldown.get(gm, (0, ""))
            if until > time.time():
                notes.append(f"{gm}: günlük sınır dolu ({when}'e kadar)")
                continue
            try:
                out = self._groq_agent_chat(mode_key, dict(mode_cfg, groq_model=gm), user_text, memory_context)
                if gm != first:
                    fx._notify(f"Groq yedek model kullanıldı: {gm}")
                return out
            except Exception as e:
                if _groq_reason(e) != "Groq günlük sınırı doldu":
                    raise
                body = getattr(getattr(e, "response", None), "text", "") or ""
                secs = _groq_retry_seconds(body)
                when = f"{_dt.datetime.now() + _dt.timedelta(seconds=secs):%H:%M}"
                cooldown[gm] = (time.time() + secs, when)
                notes.append(f"{gm}: günlük sınır doldu ({when}'e kadar)")
                fx.report_error("Groq", f"{gm}: günlük sınır doldu, {when}'e kadar atlanıyor; yedek modele geçiliyor")
        raise GroqLimit("Groq günlük sınırı doldu (" + "; ".join(notes) + ")")

    def _gemini_after_groq(self, groq_error, gemini_call):
        """Groq başarısız olunca Gemini'ye geçer; Groq'un sebebi hata notlarına yazılır. Gemini de olmazsa
        iki sebep birlikte söylenir (önceden sadece Gemini'nin 'kota doldu' hatası görünüyordu)."""
        reason = _groq_reason(groq_error)
        body = (getattr(getattr(groq_error, "response", None), "text", "") or "")[:300]
        fx.report_error("Groq", f"{reason} -> Gemini'ye geçildi. {str(groq_error)[:200]} {body}")
        print(f"[GROQ UYARI] {reason} -> Gemini'ye düşülüyor")
        try:
            return gemini_call()
        except GeminiUnavailable as ge:
            raise GeminiUnavailable(f"Groq: {reason}. Gemini: {ge.summary}", ge.last)

    def analyze_text(self, mode_key, mode_cfg, prompt):
        """Araçsız, saf metin analizi (web analizi raporu gibi). Groq varsa Groq, yoksa Gemini."""
        provider = mode_cfg.get("provider", "gemini")
        gem = lambda: self._gemini_try(
            self._gemini_models(mode_cfg["gemini_model"]),
            lambda client, model, ki: client.models.generate_content(model=model, contents=prompt).text)
        if provider in ("groq", "nvidia") and (self.groq_api_key or self._nvidia_models()):
            try:
                return self.complete(mode_cfg, prompt, system=build_system_instruction(mode_key, mode_cfg),
                                     gemini_fallback=False)
            except Exception as e:
                return self._gemini_after_groq(e, gem)
        return gem()
