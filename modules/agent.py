# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Ajan Çekirdeği
--------------
Kullanıcı girdisini alır, niyeti kabaca sınıflandırır ve uygun akışı çalıştırır.

Niyetler:
- not        : "not al: ..." / "... not et" -> Geçmiş'e not olarak kaydeder
- gun_ozet   : "bugün ne yaptık özetle" -> o günün kayıtlarından özet çıkarıp not olarak saklar
- web_analiz : "şu siteyi analiz et" -> Normal: tek sayfa rapor; Devil: çok sayfalı site denetimi
- derin      : Devil modda araştırma istekleri -> research.DeepResearch (plan, çoklu arama,
               paralel okuma, not çıkarma, eksik kontrolü, kaynaklı rapor dosyası)
- normal     : diğer her şey -> LLM (araçlı, ekran görebilir)

İlerleme bildirimi iki callback ile yapılır:
  on_plan(steps)  : görevin adım listesi (UI bunu onay kutulu liste olarak çizer)
  on_stage(name)  : şu an çalışan adım (listedeki adlardan biri)
Görevin bitişi (başarılı ya da hatalı) çağıran taraf (UI) tarafından garanti edilir.
"""
import os
import re
import json
import time
import datetime

from . import web_analyzer as wa
from .research import DeepResearch, Cancelled
from . import attachments as att
from . import macros
from . import functions as fx
from . import command_memory as cm


URL_RE = re.compile(r"(https?://[^\s]+|\b[\w\-]+\.(com|net|org|io|dev|tr|gov|edu|co)[^\s]*)", re.IGNORECASE)
ANALYZE_WORDS = ["araştır", "kontrol et", "analiz", "incele", "raporla", "rapor çıkar", "denetle", "tara", "sorunları", "açıkları"]
# Devil modda derin araştırmayı tetikleyen kelimeler
RESEARCH_WORDS = ["araştır", "araştırma", "incele", "analiz", "karşılaştır", "kıyasla", "rapor",
                  "derinlemesine", "detaylı", "ayrıntılı", "kapsamlı", "en iyi", "hangisi", "piyasa", "trend"]
SCREEN_WORDS = ["ekrana bak", "ekranıma bak", "ekranımda", "ekranda", "ekrandaki", "ekranı gör", "ekranımı",
                "şu ekran", "bu ekran", "bu hata", "burada ne", "görüyor musun", "ne yazıyor"]

# Not alma kalıpları (sesli komutta noktalama olmadığı için boşluk/iki nokta ikisi de kabul edilir)
NOTE_PATTERNS = [
    re.compile(r"^\s*(?:şunu\s+|bunu\s+)?not\s+(?:al|et|düş)\b[\s:,\-]*(.+)$", re.IGNORECASE | re.DOTALL),
    re.compile(r"^\s*(?:notlara|geçmişe|geçmişe\s+not\s+olarak)\s+(?:ekle|yaz|kaydet)\b[\s:,\-]*(.+)$",
               re.IGNORECASE | re.DOTALL),
    re.compile(r"^\s*not\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL),
    re.compile(r"^(.+?)[,\s]+(?:diye\s+)?not\s+(?:al|et|düş)[.!]?\s*$", re.IGNORECASE | re.DOTALL),
]


# Bağlamlı kısa komutlar (v5.10.1): uygulama adı verilmeyen "bunu kapat" ve "ne çalışıyor" gibi. Katlanmış (ASCII, küçük harf)
# metinle eşleşir; cümlede fazladan kelime varsa eşleşmez ve normal akışa (yapay zekâ) gidilir.
_CTX_CLOSE = re.compile(r"^(?:lutfen )?(?:bunu|sunu|onu|bu (?:uygulamayi|programi|pencereyi)|su (?:uygulamayi|programi|pencereyi)|"
                        r"ondeki (?:pencereyi|uygulamayi|programi)|acik olani) (?:kapat|kapatsana|kapatir misin|kapatabilir misin)$")
_CTX_RUNNING = re.compile(r"^(?:simdi |su an )?(?:ne|neler|hangi (?:uygulama|program)lar?) (?:calisiyor|acik)(?: su an)?$|"
                          r"^acik (?:uygulama|program)lar(?:i|im)?(?: neler)?$")
_CTX_SLOW = re.compile(r"^(?:bilgisayar(?:im)?|pc|laptop|sistem) (?:cok )?(?:yavasladi|yavas|kasiyor|donuyor|takiliyor)$|"
                       r"^neden (?:bu kadar )?(?:yavas|kasiyor|donuyor|yavasladi)(?: bilgisayar(?:im)?)?$")


def detect_context_command(text):
    """'close' | 'running' | 'slow' | None"""
    t = " ".join(re.sub(r"[?!.,]+", " ", cm.fold(text or "")).split())
    if not t or len(t) > 60:
        return None
    if _CTX_CLOSE.match(t):
        return "close"
    if _CTX_RUNNING.match(t):
        return "running"
    if _CTX_SLOW.match(t):
        return "slow"
    return None


def detect_note(text):
    """Metin bir 'not al' komutuysa not içeriğini, değilse None döner."""
    for pat in NOTE_PATTERNS:
        m = pat.match(text.strip())
        if m:
            content = m.group(1).strip(" .:-")
            if content:
                return content
    return None


def detect_day_summary(text):
    """'bugün ne yaptık' / 'dünü özetle' gibi isteklerde hedef günü (ISO) döner, yoksa None."""
    t = text.lower()
    wants = ("ne yaptık" in t) or ("özetle" in t) or ("özet çıkar" in t) or ("özeti" in t)
    if not wants:
        return None
    today = datetime.date.today()
    if "dün" in t:
        return (today - datetime.timedelta(days=1)).isoformat()
    if "bugün" in t:
        return today.isoformat()
    return None


def detect_intent(text):
    t = text.lower()
    url_match = URL_RE.search(text)
    if url_match and any(w in t for w in ANALYZE_WORDS):
        return ("web_analiz", url_match.group(0))
    return ("normal", None)


RETRY_WORDS = ["tekrar dene", "yeniden dene", "bir daha dene", "tekrar araştır", "yeniden araştır",
               "tekrar denermisin", "tekrar dener misin", "bir daha bak", "tekrar bak"]


def wants_retry(text):
    t = text.lower()
    return len(t) < 60 and any(w in t for w in RETRY_WORDS)


def wants_deep_research(text):
    """Ön eleme: araştırmayla ilgili bir kelime geçiyor mu? (Kesin karar classify ile verilir.)"""
    t = text.lower()
    return any(w in t for w in RESEARCH_WORDS)


THANKS_RE = re.compile(r"teşekkür|tesekkur|sağ ?ol|sag ?ol|eyvallah|eline sağlık|harika olmuş|güzel olmuş|süper olmuş",
                       re.IGNORECASE)
# Emir kipindeki araştırma fiilleri ("inceleme yapılan", "araştırma güzeldi" gibi isimleri yakalamaz)
COMMAND_RE = re.compile(r"(araştır(?!ma\b|man\b|ması)|incele(?!me)|analiz et|karşılaştır|kıyasla|"
                        r"rapor(?:la| çıkar| hazırla| yaz)|derinlemesine bak)", re.IGNORECASE)


def looks_like_research_command(text):
    """Model sınıflandırması yapılamazsa kullanılan yedek kural."""
    t = text.lower()
    if not COMMAND_RE.search(t):
        return False
    if THANKS_RE.search(t) and not re.search(r"\b(şimdi|bir de|ayrıca|şunu da)\b", t):
        return False
    return True


# Sadece açık "ekranıma bak" türü istekler (uzun bir mesajın içinde 'ekran' kelimesi geçmesi yetmez;
# diğer durumlarda model gerekirse look_at_screen aracını kendisi çağırır)
_SCREEN_RE = re.compile(
    r"ekran(ım|ımı|ıma|ımda|ımdaki|ı|a|da|daki|ında|ındaki)\s*(ne\b|neler|bak|gör|oku|incele|kontrol|var|yaz)|"
    r"ekran(ımdaki|daki|ındaki)\b|\bbu hata\b|burada ne|ne görüyorsun|neye bakıyorum|şuna bak\b|buna bak\b|"
    r"(ekranı|ekranımı|bunu|şunu)?\s*görüyor musun|görebiliyor musun", re.IGNORECASE)


def wants_screen(text):
    """Mesaj ekrandan bahsediyor mu? ('ekran kartı' gibi ifadeler sayılmaz.) Diğer durumlarda model
    look_at_screen aracını kendisi çağırabilir."""
    t = text.lower().replace("i̇", "i")
    if len(t) > 220:                   # uzun metinler (yapıştırılmış yazılar) otomatik ekran yakalamasın
        return False
    return bool(_SCREEN_RE.search(t))


_LIST_RE = re.compile(r"öğrendik(?:lerim|lerin|lerini|leri)\b|öğrendiğin komut|hatırladığın komut|komut hafıza")
_FORGET_RE = re.compile(r"^[\"“']?(.+?)[\"”']?\s+(?:komutunu|komutu|kalıbını|kalıbı)\s+(?:unut|sil)$")
_RESET_RE = re.compile(r"^(?:öğrendiğin|öğrendiklerini|öğrendiklerimi|komut hafızanı|hafızadaki komutları)\s*(?:komutları\s*)?"
                       r"(?:hepsini\s*)?(?:sıfırla|temizle|sil|unut)$")
_SCAN_RE = re.compile(r"^(?:bilgisayarı|bilgisayarımı|pc'?yi|pc yi|uygulamaları)\s+(?:yeniden\s+)?(?:tara|öğren)\b")
_TRAIN_RE = re.compile(r"^(?:kendini|komutları|komut)\s*(?:eğit|öğren)|eğitim turu|komut eğitimi")
_FEEDBACK_RE = re.compile(r"^(?:hayır[,\s]*)?(?:yanlış (?:anladın|yaptın|oldu|komut)|öyle değil|bunu öğrenme|bunu unut)\b")




class Agent:
    def __init__(self, llm, memory, on_stage=None, on_plan=None, notify=None, cancelled=None,
                 research_cfg=None, command_cfg=None):
        self.llm = llm
        self.memory = memory
        self.on_stage = on_stage or (lambda name: None)
        self.on_plan = on_plan or (lambda steps: None)
        self.notify = notify or (lambda text: None)
        self.cancelled = cancelled or (lambda: False)
        self.research_cfg = research_cfg or {}
        self._last_research = None      # "tekrar dene" için son derin araştırma isteği
        self.command_cfg = command_cfg or {}     # config.yaml -> komut_hafizasi
        self._last_local = None         # son hafızadan çalışan komut: {"id", "t"} ('yanlış anladın' için)

    def _classify_research(self, text, mode_cfg, context=""):
        """Mesaj gerçekten YENİ bir araştırma isteği mi? Teşekkür, geri bildirim, önceki cevap hakkında
        yorum gibi mesajlar kelime içerse bile araştırma başlatmaz. Döner: (araştırma_mı, net_konu)."""
        prompt = (
            (f"[Son konuşma]\n{context[:2500]}\n\n" if context else "") +
            f"Kullanıcının YENİ mesajı: {text}\n\n"
            "Bu mesaj senden YENİ bir web araştırması/analizi yapmanı mı istiyor?\n"
            "Teşekkür, övgü, geri bildirim, üslup/biçim isteği (ör. 'kaynakları okuma'), önceki cevap hakkında "
            "yorum, basit sohbet sorusu veya bilgisayar komutu ise araştırma DEĞİLDİR.\n"
            'SADECE JSON döndür: {"arastirma": true/false, "konu": "araştırılacaksa konu; bağlamdaki site/şirket '
            'adı ve adresiyle birlikte net bir cümle"}')
        try:
            out = self.llm.complete(mode_cfg, prompt, fast=True,
                                    fast_model=self.research_cfg.get("fast_model", "openai/gpt-oss-20b"))
            m = re.search(r"\{.*\}", out or "", re.DOTALL)
            data = json.loads(m.group(0)) if m else None
        except Exception as e:
            print(f"[NİYET] sınıflandırma yapılamadı: {e}")
            data = None
        if not isinstance(data, dict) or "arastirma" not in data:
            return looks_like_research_command(text), text
        konu = data.get("konu") if isinstance(data.get("konu"), str) and len(data.get("konu", "")) > 5 else text
        return bool(data["arastirma"]), konu

    # ------------------------------------------------------------------
    def _doc_cfg(self):
        d = {"direct_chars": 12000, "chunk_chars": 8000, "max_chunks": 40}
        d.update(self.research_cfg.get("documents", {}) if isinstance(self.research_cfg.get("documents"), dict) else {})
        return d

    def _handle_attachments(self, user_text, attachments, mode_key, mode_cfg):
        """Ekli dosyalarla cevap verir.
        - Küçük metin: doğrudan mesaja eklenir (araçlı normal akış, resimler görüntü modeline).
        - Büyük metin: parça parça okunur (hızlı model her parçadan not çıkarır), notlarla cevap yazılır.
        - Devil + rapor/analiz isteği: kaynaklı belge raporu yazılır, Raporlarım'a kaydedilir."""
        cfg = self._doc_cfg()
        question = user_text.strip() or "Bu dosyaları incele: ne olduklarını ve ana noktalarını özetle."
        texts = [a for a in attachments if a.get("kind") == "text" and a.get("text", "").strip()]
        image_items = [a for a in attachments if a.get("kind") == "image" and a.get("image_b64")]
        images = [a["image_b64"] for a in image_items]
        warnings = [f"{a['name']}: {a['note']}" for a in attachments if a.get("note")]
        names = ", ".join(a["name"] for a in attachments)
        total = sum(len(a["text"]) for a in texts)
        want_report = mode_key == "devil" and re.search(r"rapor|analiz|değerlendir|degerlendir|detaylı incele",
                                                       question.lower())
        warn_txt = ("\n\n⚠️ " + " | ".join(warnings)) if warnings else ""

        if not texts and not images:
            return "Eklenen dosyalardan okunabilir içerik çıkmadı." + warn_txt

        # --- küçük belge(ler): doğrudan ---
        # Görseller Gemini'ye bir kez tarif ettirilir; sohbet ve araçlar normal modelde (Groq) sürer
        image_descs = []
        if image_items:
            self._plan((["Dosya okunuyor"] if texts else []) + ["Görsel inceleniyor", "Yanıt hazırlanıyor"])
            self._stage("Görsel inceleniyor")
            for a in image_items:
                try:
                    image_descs.append((a["name"], fx.describe_image_b64(a["image_b64"], question, a["name"])))
                except fx.VisionError as e:
                    if not texts and len(image_items) == 1:
                        return str(e) + warn_txt
                    image_descs.append((a["name"], f"(okunamadı: {e})"))
        img_block = "\n\n".join(f"=== {n} (görsel; FENIX'in gördüğü) ===\n{d}" for n, d in image_descs)

        if total <= cfg["direct_chars"] and not want_report:
            if not image_items:
                self._plan(["Dosya okunuyor", "Yanıt hazırlanıyor"])
            if texts:
                self._stage("Dosya okunuyor")
            blocks = "\n\n".join(f"=== {a['name']} ({a.get('info', '')}) ===\n{a['text']}" for a in texts)
            if img_block:
                blocks = (blocks + "\n\n" + img_block).strip()
            msg = question + (f"\n\n[EKLİ DOSYALAR]\n{blocks}" if blocks else "")
            self._stage("Yanıt hazırlanıyor")
            look = (question + " " + " ".join(a["text"][:1500] for a in texts)).strip()   # dersler dosya içeriğine göre de bulunsun
            answer = self.llm.ask(mode_key, mode_cfg, msg,
                                  memory_context=self.memory.get_context(look) if self.memory else "")
            try:
                self.llm.compact_last_user(mode_key, f"{question}\n[Ekli dosyalar okundu: {names}]")
            except Exception:
                pass
            return (answer or "") + warn_txt

        # --- büyük belge(ler) veya rapor: parça parça ---
        steps = ["Dosya okunuyor", "Parçalar inceleniyor", "Yanıt hazırlanıyor"]
        if want_report:
            steps = ["Dosya okunuyor", "Parçalar inceleniyor", "Rapor yazılıyor", "Rapor kaydediliyor"]
        self._plan(steps)
        self._stage("Dosya okunuyor")
        chunks = []
        for a in texts:
            parts = att.chunk_text(a["text"], cfg["chunk_chars"])
            for i, c in enumerate(parts, 1):
                chunks.append((f"{a['name']} | parça {i}/{len(parts)}", c))
        truncated = len(chunks) > cfg["max_chunks"]
        chunks = chunks[:cfg["max_chunks"]]
        self.notify(f"{len(texts)} dosya, {total:,} karakter → {len(chunks)} parça".replace(",", "."))

        self._stage("Parçalar inceleniyor")
        researcher = self._researcher()
        notes = [None] * len(chunks)

        def work(i):
            if self.cancelled():
                return i, ""
            label, body = chunks[i]
            prompt = (f"KULLANICININ İSTEĞİ: {question}\n\nAşağıda bir belgenin bir parçası var ({label}). "
                      "Bu parçadan istekle ilgili bilgileri kısa maddeler halinde çıkar; sayfa/tablo/bölüm "
                      "bilgisi varsa koru (ör. 'Sayfa 4'). İstek genel bir özet ise parçanın ana fikirlerini, "
                      "önemli sayıları ve isimleri çıkar. Parçada olmayanı ekleme.\n\n" + body)
            try:
                return i, self.llm.complete(mode_cfg, prompt, fast=True,
                                            fast_model=self.research_cfg.get("fast_model", "openai/gpt-oss-20b"))
            except Exception as e:
                print(f"[BELGE] parça okunamadı: {e}")
                return i, ""

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as ex:
            for done, (i, txt) in enumerate(ex.map(work, range(len(chunks))), 1):
                notes[i] = f"[{chunks[i][0]}]\n{txt}" if txt else ""
                self.notify(f"📄 parça {done}/{len(chunks)} okundu")
                if self.cancelled():
                    raise Cancelled()
        notes = [n for n in notes if n]
        if img_block:
            notes.append(f"[Ekli görseller]\n{img_block}")
        if not notes:
            raise RuntimeError("Belge parçalarından not çıkarılamadı")
        joined = "\n\n".join(notes)[:30000]
        trunc_txt = (f"\n\n(Not: belge çok uzun olduğu için ilk {cfg['max_chunks']} parça incelendi.)"
                     if truncated else "")

        if not want_report:
            self._stage("Yanıt hazırlanıyor")
            answer = self.llm.complete(mode_cfg, (
                f"KULLANICININ İSTEĞİ: {question}\nDOSYALAR: {names}\n\nBELGEDEN ÇIKARILAN NOTLAR:\n{joined}\n\n"
                "Bu notlara dayanarak isteği Türkçe, net ve eksiksiz cevapla. Notlarda olmayan bilgiyi uydurma. "
                "Markdown işaretleri kullanma, düz yaz."),
                system="Sen FENIX'sin; kullanıcının belgelerini okuyup net, doğru cevap verirsin.")
            return (answer or "") + trunc_txt + warn_txt

        self._stage("Rapor yazılıyor")
        report = self.llm.complete(mode_cfg, (
            f"KULLANICININ İSTEĞİ: {question}\nDOSYALAR: {names}\n\nBELGEDEN ÇIKARILAN NOTLAR:\n{joined}\n\n"
            "Bu notlara dayanarak Türkçe bir BELGE ANALİZ RAPORU yaz (Markdown):\n# <başlık>\n## Özet\n"
            "(3-5 cümle)\n## Ana Bulgular\n## Ayrıntılar\n(gerekirse tablo)\n## Eksikler / Riskler / Tutarsızlıklar\n"
            "## Öneriler\nHer bilginin yanına parça/sayfa bilgisini yaz, örn. (Sayfa 4). Uydurma."),
            system="Sen titiz bir belge analistisin. Türkçe, net ve kaynak gösteren raporlar yazarsın.")
        self._stage("Rapor kaydediliyor")
        title_m = re.search(r"^#\s+(.+)$", report or "", re.MULTILINE)
        title = (title_m.group(1).strip() if title_m else f"Belge analizi {names}")[:80]
        full = (f"{(report or '').strip()}\n\n## İncelenen Dosyalar\n" +
                "\n".join(f"- {a['name']} ({a.get('info', '')})" for a in attachments) +
                f"\n\n---\n_{len(chunks)} parça incelendi • FENIX Devil mod_\n")
        path = researcher._save(title, full)
        if self.memory:
            self.memory.log_event("rapor", f"{title} -> {path}")
        summary = DeepResearch._summary_of(report or "")
        return {"text": f"{summary}\n\n📄 Belge raporu açıldı ve kaydedildi: {path}{trunc_txt}{warn_txt}",
                "speak": summary, "report_title": title, "report": full, "report_path": path}

    def run_macro(self, name, steps, mode_key, mode_cfg):
        """Kısayolun adımlarını sırayla çalıştırır; her adım normal bir komut gibi işlenir."""
        self._plan([f"{i}. {st}" for i, st in enumerate(steps, 1)])
        results = []
        for i, step in enumerate(steps, 1):
            if self.cancelled():
                results.append(f"{i}. {step} — durduruldu")
                break
            self._stage(f"{i}. {step}")
            try:
                out = self.llm.ask(mode_key, mode_cfg,
                                   f"{step}\n(Bu, '{name}' kısayolunun {i}/{len(steps)}. adımı. Sadece bu adımı yap, "
                                   "tek cümleyle sonucu söyle.)")
                short = " ".join((out or "").split())[:140]
                results.append(f"{i}. {step} — {short}")
            except Exception as e:
                from . import functions as _fx
                _fx.report_error(f"kısayol '{name}'", e)
                results.append(f"{i}. {step} — hata ile karşılaştım")
        if self.memory:
            self.memory.log_event("kisayol", f"{name}: {len(steps)} adım")
        return {"text": f"⚡ '{name}' kısayolu çalıştı:\n" + "\n".join(results),
                "speak": f"{name} tamamlandı."}

    def _researcher(self):
        return DeepResearch(self.llm, self.research_cfg, on_stage=self._stage, on_plan=self._plan,
                            notify=self.notify, cancelled=self.cancelled)

    def _deep(self, fn):
        """Derin araştırmayı çalıştırır; iptal edilirse nazikçe döner, olay kaydı düşer."""
        try:
            result = fn()
        except Cancelled:
            return {"text": "Araştırmayı durdurdum.", "speak": "Araştırmayı durdurdum."}
        if self.memory and isinstance(result, dict) and result.get("report_path"):
            self.memory.log_event("rapor", f"{result.get('report_title')} -> {result['report_path']}")
        return result

    def _plan(self, steps):
        try:
            self.on_plan(steps)
        except Exception:
            pass

    def _stage(self, name):
        try:
            self.on_stage(name)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # v5.9.0: komut hafızası
    def _cm_enabled(self):
        return bool(self.command_cfg.get("etkin", True))

    def _fast_model(self):
        return self.research_cfg.get("fast_model", "openai/gpt-oss-20b")

    def _memory_commands(self, text, mode_cfg):
        """Komut hafızasının kendi yönetim komutları: listele, eğit, tara, unut, sıfırla, 'yanlış anladın'."""
        t = text.lower().strip().rstrip(".!")
        if self._last_local and time.time() - self._last_local["t"] < 90 and _FEEDBACK_RE.search(t):
            eid, self._last_local = self._last_local["id"], None
            cm.remove(eid)
            return "Tamam, bu kalıbı unuttum. Bir dahaki sefere yeniden sorarım."
        if _RESET_RE.search(t):
            if not fx._confirm("Öğrenilen komutlar silinecek", "Hafızadaki bütün komut kalıpları silinsin mi?",
                               "Eğitim turu bir sonraki açılışta yeniden yapılır."):
                return "Silmedim."
            return f"{cm.clear_all()} komut kalıbını sildim."
        m = _FORGET_RE.search(t)
        if m:
            n = cm.remove_matching(m.group(1))
            return (f"'{m.group(1)}' ile ilgili {n} kalıbı unuttum." if n else
                    f"'{m.group(1)}' diye öğrenilmiş bir komut bulamadım.")
        if _LIST_RE.search(t) and len(t) < 70:
            return cm.summary_text(fx.FUNCTION_SCHEMAS)
        if _SCAN_RE.search(t) and len(t) < 60:
            self._plan(["Bilgisayar taranıyor"])
            self._stage("Bilgisayar taranıyor")
            r = fx.WHITELISTED_FUNCTIONS["scan_pc"]()
            return r.get("message", "Taradım.")
        if _TRAIN_RE.search(t) and len(t) < 60:
            return self.train_commands(mode_cfg)
        return None

    def train_commands(self, mode_cfg, background=False):
        """Eğitim turu: bekleyen araçlar için söylenişleri (yalnızca Groq hızlı modeli) üretip hafızaya yazar."""
        from . import pc_tools
        if not background:
            self._plan(["Bilgisayar taranıyor", "Söylenişler üretiliyor"])
            self._stage("Bilgisayar taranıyor")
        try:
            if os.name == "nt" and (pc_tools.inventory_age_days() is None or pc_tools.inventory_age_days() > 7):
                pc_tools.scan_pc()
        except Exception as e:
            print(f"[KOMUT HAFIZASI] tarama: {e}")
        if not background:
            self._stage("Söylenişler üretiliyor")
        res = cm.train(self.llm, mode_cfg, fx.FUNCTION_SCHEMAS, fast_model=self._fast_model(),
                       cancelled=self.cancelled,
                       on_progress=lambda name, n: self.notify(f"Komut hafızası: {name} → {n} söyleniş"))
        if background:
            return res
        parts = [f"{res['eklenen']} yeni söyleniş öğrendim."]
        if res["kalan"]:
            parts.append(f"Henüz tamamlanmayan araçlar: {', '.join(res['kalan'])}.")
        if res["durdu"]:
            parts.append(f"Durma sebebi: {res['durdu']}. Kalanları sonra yeniden denerim ('kendini eğit' demen yeterli).")
        if not res["eklenen"] and not res["kalan"] and not res["durdu"]:
            parts = ["Bütün araçların söylenişlerini zaten öğrenmiştim."]
        return " ".join(parts)

    def _try_context(self, text, mode_cfg):
        """Uygulama adı vermeyen kısa komutlar yapay zekâya sorulmadan çalışır. 'bunu kapat' işlem yapar (Güvenli modda
        yapmaz); 'ne çalışıyor' / 'yavaşladı' yalnızca okur. Döner: cevap metni ya da None."""
        kind = detect_context_command(text)
        if kind is None:
            return None
        if kind == "close" and not mode_cfg.get("allow_actions"):
            return "Güvenli moddayım, pencere kapatmıyorum. Normal moda geçersen kapatırım."
        tool, args = {"close": ("close_front_app", {}), "running": ("pc_awareness", {"kind": "running"}),
                      "slow": ("pc_awareness", {"kind": "slow"})}[kind]
        fn = fx.WHITELISTED_FUNCTIONS.get(tool)
        if not fn:
            return None
        label = {"close": "Öndeki pencereyi kapat", "running": "Açık uygulamalara bak", "slow": "Bilgisayara bak"}[kind]
        self._plan([label])
        self._stage(label)
        old = fx._speak
        fx._speak = lambda *a, **k: None          # cevabı uygulama okur
        try:
            result = fn(**args)
        except Exception as e:
            fx.report_error(f"bağlamlı komut: {tool}", e)
            return None
        finally:
            fx._speak = old
        if not isinstance(result, dict) or not result.get("message"):
            return None
        if self.memory:
            try:
                self.memory.log_event("yerel_komut", f"{text[:60]} -> {tool}")
            except Exception:
                pass
        return result["message"]

    def _try_local(self, text, mode_cfg, force_screen=False):
        """Hafızadaki bir komutla tamamen eşleşiyorsa aracı yapay zekâya sormadan çalıştırır. Döner: cevap ya da None."""
        if not self._cm_enabled() or len(text) > 90:
            return None
        r = self._memory_commands(text, mode_cfg)
        if r is not None:
            return r
        if force_screen or not mode_cfg.get("allow_actions"):
            return None
        hit = cm.find(text, allowed=set(fx.WHITELISTED_FUNCTIONS))
        if not hit:
            return None
        entry, args = hit
        self._plan(["Hatırladığım komut"])
        self._stage("Hatırladığım komut")
        result = cm.execute(entry["arac"], args)
        reply = cm.reply_text(entry["arac"], args, result)
        if reply is None:
            return None                  # bulunamadı / hata: normal akışa (yapay zekâ) bırak
        if cm.result_ok(entry["arac"], result):
            cm.record_use(entry["id"])
            self._last_local = {"id": entry["id"], "t": time.time()}
        if self.memory:
            try:
                self.memory.log_event("yerel_komut", f"{entry['gorunen']} -> {entry['arac']}")
            except Exception:
                pass
        return reply

    def _learn(self, text, mode_cfg):
        if not self._cm_enabled() or not mode_cfg.get("allow_actions"):
            return
        try:
            cm.learn(text, list(getattr(self.llm, "last_calls", []) or []), llm=self.llm, mode_cfg=mode_cfg,
                     fast_model=self._fast_model(), sync=bool(self.command_cfg.get("_sync")))
        except Exception as e:
            print(f"[KOMUT HAFIZASI] {e}")

    # ------------------------------------------------------------------
    def handle(self, user_text, mode_key, mode_cfg, force_screen=False, attachments=None):
        """Girdiyi işleyip metin cevabı döner. UI bunu worker thread'de çağırır."""
        # 0) Ekli dosyalar varsa önce onlar.
        if attachments:
            try:
                return self._handle_attachments(user_text, attachments, mode_key, mode_cfg)
            except Cancelled:
                return {"text": "Dosya incelemesini durdurdum.", "speak": "Durdurdum."}
        # 1) Not alma
        note = detect_note(user_text)
        if note is not None:
            self._plan(["Notu al", "Geçmişe kaydet"])
            self._stage("Notu al")
            self._stage("Geçmişe kaydet")
            self.memory.add_note(note, source="user")
            return f"Notu geçmişe ekledim: {note}"

        # 1b) Kısayol komutu ("çalışma modu" gibi kayıtlı çok adımlı komutlar)
        hit = macros.match(user_text)
        if hit:
            return self.run_macro(hit[0], hit[1], mode_key, mode_cfg)

        # 1b2) Bağlamlı komutlar: "bunu kapat", "ne çalışıyor", "bilgisayar yavaşladı" (v5.10.1)
        ctx = self._try_context(user_text, mode_cfg)
        if ctx is not None:
            try:
                self.llm.remember_exchange(mode_key, user_text, ctx)
            except Exception:
                pass
            return ctx

        # 1c) Komut hafızası: öğrenilmiş kısa komutlar yapay zekâya sorulmadan çalışır (v5.9.0)
        local = self._try_local(user_text, mode_cfg, force_screen)
        if local is not None:
            try:
                self.llm.remember_exchange(mode_key, user_text, local)
            except Exception:
                pass
            return local

        # 2) Gün özeti
        day = detect_day_summary(user_text)
        if day:
            return self.summarize_day(day, mode_key, mode_cfg)

        intent, payload = detect_intent(user_text)

        # 3) Devil mod: derin araştırma / çok sayfalı site denetimi
        if mode_key == "devil":
            if wants_retry(user_text) and self._last_research:
                kind, arg = self._last_research
                if kind == "site":
                    return self._deep(lambda: self._researcher().site_audit(arg, arg, mode_cfg))
                user_text = arg
                intent = "normal"
                force_research = True
            else:
                force_research = False
            candidate = intent == "web_analiz" or (
                wants_deep_research(user_text) and not (force_screen or wants_screen(user_text)))
            if force_research or candidate:
                context = ""
                try:
                    context = self.memory.get_context(user_text) if self.memory else ""
                except Exception:
                    pass
                if force_research:
                    is_research, topic = True, user_text
                else:
                    is_research, topic = self._classify_research(user_text, mode_cfg, context)
                if is_research and intent == "web_analiz":
                    self._last_research = ("site", payload)
                    return self._deep(lambda: self._researcher().site_audit(payload, topic, mode_cfg))
                if is_research:
                    self._last_research = ("research", topic)
                    return self._deep(lambda: self._researcher().run(topic, mode_cfg, context=context))
                intent = "normal"     # araştırma değil: normal sohbet akışına devam

        # 4) Web analizi (tek sayfa; Normal mod)
        if intent == "web_analiz":
            if mode_cfg.get("allow_actions"):
                return self._run_web_analysis(payload, user_text, mode_key, mode_cfg)
            return ("Site analizi bu modda kapalı. Normal ya da Devil moda geçersen "
                    "siteyi analiz edip rapor çıkarabilirim.")

        # 5) Normal akış
        want_screen = force_screen or wants_screen(user_text)
        steps = ["Anlıyorum"] + (["Ekran yakalanıyor"] if want_screen else []) + ["Yanıt hazırlanıyor"]
        self._plan(steps)
        self._stage("Anlıyorum")
        memory_context = self.memory.get_context(user_text) if self.memory else ""

        message = user_text
        if want_screen:
            # Ekran Gemini'ye bir kez tarif ettirilir; sohbet (ve araçlar) normal modelde devam eder.
            self._stage("Ekran yakalanıyor")
            try:
                seen = fx.describe_screen(user_text)
                message = f"{user_text}\n\n[Ekranın şu anki görüntüsü (FENIX'in gördüğü)]\n{seen}"
            except fx.VisionError as e:
                # Ekran okunamasa da soruyu cevaplamaya devam et; sebebi modele ilet
                message = (f"{user_text}\n\n[Sistem notu: ekran görüntüsü yorumlanamadı — {e} Kullanıcı ekranla "
                           "ilgili bir şey sorduysa bunu kısaca söyle; değilse soruyu normal cevapla.]")

        self._stage("Yanıt hazırlanıyor")
        answer = self.llm.ask(mode_key, mode_cfg, message, memory_context=memory_context)
        if want_screen:
            try:
                self.llm.compact_last_user(mode_key, f"{user_text}\n[Ekrana bakıldı]")
            except Exception:
                pass
        elif intent == "normal":
            self._learn(user_text, mode_cfg)        # tek araçlı başarılı kısa komutsa hafızaya yaz
        return answer

    # ------------------------------------------------------------------
    def summarize_day(self, day, mode_key, mode_cfg, session_id=None, session_title=None):
        """Bir günün (session_id verilirse sadece o sohbetin o günkü) kayıtlarından özet çıkarır ve not olarak saklar."""
        self._plan(["Kayıtlar toplanıyor", "Özet yazılıyor", "Geçmişe kaydet"])
        self._stage("Kayıtlar toplanıyor")
        data = self.memory.get_day_events(day, session_id=session_id)
        activity = {} if session_id is not None else self.memory.get_activity_summary(day)

        if not (data["conversations"] or data["events"] or data["notes"] or activity):
            return f"{day} tarihi için henüz kayıt yok, özetleyecek bir şey bulamadım."

        lines = [f"Tarih: {day}"] + ([f"Sohbet: {session_title}"] if session_title else [])
        if activity:
            lines.append("Ekran kategorileri (dk): " + ", ".join(f"{c}: {m}" for c, m in activity.items()))
        if data["notes"]:
            lines.append("Notlar:")
            lines += [f"- {c}" for _, _, c in data["notes"]]
        if data["events"]:
            lines.append("Yapılan işlemler:")
            lines += [f"- {k}: {d}" for _, k, d in data["events"][:40]]
        if data.get("sessions"):
            lines.append("Sohbetler (konu başlığına göre, kısaltılmış):")
            for g in data["sessions"]:
                lines.append(f"* Sohbet: {g['title']} ({len(g['messages'])} mesaj)")
                for ts, role, content in g["messages"][-8:]:
                    lines.append(f"  - {'Kullanıcı' if role == 'user' else 'FENIX'}: {content[:160]}")
        elif data["conversations"]:
            lines.append("Konuşmalar (kısaltılmış):")
            for ts, role, content in data["conversations"][-30:]:
                lines.append(f"- {'Kullanıcı' if role == 'user' else 'FENIX'}: {content[:160]}")

        prompt = ("Aşağıda kullanıcının bir günlük kayıtları var. Türkçe, kısa ve net bir GÜN ÖZETİ yaz: "
                  "hangi sohbetlerde (konu başlıklarıyla) ne üzerinde çalışıldı, hangi kararlar/işlemler yapıldı, "
                  "açık kalan işler neler. "
                  "En fazla 8 cümle, madde işareti kullanma.\n\n" + "\n".join(lines))
        self._stage("Özet yazılıyor")
        summary = self.llm.analyze_text(mode_key, mode_cfg, prompt)

        self._stage("Geçmişe kaydet")
        label = f"[{day} • {session_title} özeti]" if session_title else f"[{day} özeti]"
        self.memory.add_note(f"{label} {summary}", source="summary")
        return summary

    def _run_web_analysis(self, url, user_goal, mode_key, mode_cfg):
        steps = ["Hedef analizi", "Sayfa çekiliyor", "Yapı & içerik taranıyor", "Rapor derleniyor"]
        self._plan(steps)
        self._stage("Hedef analizi")
        if self.memory:
            self.memory.log_event("web_analiz", url)
        self._stage("Sayfa çekiliyor")
        report = wa.fetch_and_parse(url)
        if "error" in report:
            return f"Siteyi analiz edemedim: {report['error']}"
        self._stage("Yapı & içerik taranıyor")
        prompt = wa.build_analysis_prompt(report, user_goal)
        self._stage("Rapor derleniyor")
        answer = self.llm.analyze_text(mode_key, mode_cfg, prompt)
        header = (f"Site: {report['final_url']}  |  Durum: {report['status_code']}  |  "
                  f"Boyut: {report['size_kb']} KB  |  Süre: {report['elapsed_ms']} ms\n\n")
        return header + answer
