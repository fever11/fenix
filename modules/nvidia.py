# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""NVIDIA (build.nvidia.com) sağlayıcısı — v6.0. İsteğe bağlı; config.yaml'da api_keys.nvidia doluysa kullanılır.

Kullanım yeri:
- Sohbet: Groq'un modelleri dolunca / hata verince sıradaki sağlayıcı NVIDIA'dır (nvidia.chat_models), o da olmazsa Gemini.
  Modda provider: "nvidia" seçilirse NVIDIA önce denenir.
- Görme (ekran / eklenen görsel): Gemini'nin TÜM model ve anahtarları başarısız olursa EN SON görsel model
  (nemotron VL) devreye girer.
Bir model sınıra takılır ya da art arda hata verirse bir süre dinlendirilir."""
import datetime
import time

URL = "https://integrate.api.nvidia.com/v1/chat/completions"
CFG = {"key": "",
       "gorsel": "nvidia/nemotron-3.5-super-vl-120b-a12b",
       "chat": ["deepseek-ai/deepseek-v4.1-flash", "nvidia/nemotron-3.5-lightning-30b-a3b"],
       "timeout": 240}
_pause = {}          # model -> zaman (bu zamana kadar denenmez)
_fails = {}          # model -> art arda hata sayısı
_log = [None]        # günlük fonksiyonu — isteğe bağlı


def configure(cfg, log=None):
    """config.yaml: api_keys.nvidia + nvidia.{gorsel_model}"""
    if log:
        _log[0] = log
    try:
        key = ((cfg.get("api_keys") or {}).get("nvidia") or "").strip()
        CFG["key"] = "" if key.startswith("BURAYA") else key
        s = cfg.get("nvidia") or {}
        for name, k in (("gorsel_model", "gorsel"),):
            if (s.get(name) or "").strip():
                CFG[k] = s[name].strip()
        chat = [m.strip() for m in (s.get("chat_models") or []) if isinstance(m, str) and m.strip()]
        if chat:
            CFG["chat"] = chat
        if s.get("timeout_seconds"):
            CFG["timeout"] = int(s["timeout_seconds"])
    except Exception:
        CFG["key"] = ""


def chat_models():
    """Sohbette kullanılacak NVIDIA modelleri (anahtar yoksa boş)."""
    return list(CFG["chat"]) if enabled() else []


def enabled():
    return bool(CFG["key"])


def available(model):
    return enabled() and bool(model) and time.time() >= _pause.get(model, 0)


def paused_until(model):
    t = _pause.get(model, 0)
    return datetime.datetime.fromtimestamp(t) if t > time.time() else None


def _note(msg):
    if _log[0]:
        try:
            _log[0](msg)
        except Exception:
            pass
    print(f"[NVIDIA] {msg}")


def chat(model, messages, temperature=0.3, max_tokens=8000, timeout=(15, 90), extra=None):
    """Tek istek. Sınır (429) / geçersiz anahtar (401/403) / art arda hata durumunda modeli dinlendirir ve
    RuntimeError yükseltir; çağıran bir sonraki seçeneğe geçer."""
    import requests
    try:
        r = requests.post(URL, timeout=timeout,
                          headers={"Authorization": f"Bearer {CFG['key']}", "Content-Type": "application/json"},
                          json=dict({"model": model, "temperature": temperature, "max_tokens": max_tokens,
                                     "messages": messages}, **(extra or {})))
    except Exception as e:
        why = _net_reason(e)
        if "gelmedi" in why or "kurulamadı" in why:      # yavaş/ulaşılamaz: bekletmesin, hemen 15 dk dinlendir
            _pause[model] = time.time() + 900
            _note(f"{model}: {why}; 15 dk dinlendiriliyor")
        else:
            _fail(model, why)
        raise RuntimeError(f"NVIDIA {why}")
    if r.status_code == 429:
        try:
            wait = float(r.headers.get("retry-after", 0)) or 120.0
        except Exception:
            wait = 120.0
        _pause[model] = time.time() + wait
        raise RuntimeError(f"NVIDIA sınırı ({model}, {int(wait)} sn)")
    if r.status_code in (401, 403):
        models = {CFG["gorsel"], model, *CFG["chat"]}     # CFG["chat"] bir liste: set() içine doğrudan konamaz
        for m in models:
            _pause[m] = time.time() + 6 * 3600
        _note("NVIDIA anahtarı reddedildi (401/403); config.yaml'daki api_keys.nvidia değerini kontrol et")
        raise RuntimeError("NVIDIA anahtarı reddedildi")
    if r.status_code == 404:
        _pause[model] = time.time() + 6 * 3600
        _note(f"NVIDIA modeli bulunamadı: {model} (config.yaml'daki model adını build.nvidia.com'daki adla karşılaştır)")
        raise RuntimeError(f"NVIDIA modeli bulunamadı: {model}")
    if r.status_code in (502, 503, 504):          # sunucu yoğun/çökmüş: art arda 10'ar dk beklememek için hemen dinlendir
        _pause[model] = time.time() + 1800
        _fails[model] = 0
        _note(f"{model}: NVIDIA sunucusu yoğun (HTTP {r.status_code}); 30 dk dinlendiriliyor")
        raise RuntimeError(f"NVIDIA sunucusu yoğun (HTTP {r.status_code})")
    if r.status_code >= 400:
        _fail(model, f"HTTP {r.status_code}: {(r.text or '')[:120]}")
        raise RuntimeError(f"NVIDIA HTTP {r.status_code}")
    _fails[model] = 0
    return (r.json()["choices"][0]["message"].get("content") or "")


def _net_reason(e):
    """Ağ hatasının kısa Türkçe sebebi (günlükte kesilmeden okunabilsin)."""
    t = f"{type(e).__name__}: {e}"
    low = t.lower()
    if "read timed out" in low or "readtimeout" in low:
        return "20 dk içinde cevap gelmedi (sunucu çok yavaş / yoğun)"
    if "connecttimeout" in low or "connect timeout" in low:
        return "bağlantı 15 sn'de kurulamadı (ağ ya da güvenlik duvarı)"
    if "ssl" in low or "certificate" in low:
        return "SSL/sertifika hatası (antivirüs ya da ağ araya giriyor olabilir)"
    if "getaddrinfo" in low or "name resolution" in low or "nameresolution" in low:
        return "adres çözülemedi (DNS / internet)"
    if "connection" in low and ("refused" in low or "reset" in low or "aborted" in low):
        return "bağlantı reddedildi ya da koptu (ağ / güvenlik duvarı)"
    return "bağlantı hatası: " + t[-140:]


def _fail(model, why):
    _fails[model] = _fails.get(model, 0) + 1
    if _fails[model] >= 3:
        _pause[model] = time.time() + 600
        _fails[model] = 0
        _note(f"{model} art arda hata verdi, 10 dk dinlendiriliyor ({why[:80]})")


def describe_image(prompt, b64):
    """Görme için SON çare: görsel model. Önce OpenAI biçimi (image_url), kabul edilmezse eski <img> biçimi."""
    model = CFG["gorsel"]
    if not available(model):
        raise RuntimeError("NVIDIA görsel modeli kullanılamıyor")
    url = f"data:image/jpeg;base64,{b64}"
    try:
        return chat(model, [{"role": "user", "content": [{"type": "text", "text": prompt},
                                                          {"type": "image_url", "image_url": {"url": url}}]}],
                    temperature=0.2, max_tokens=2000)
    except RuntimeError as e:
        if "HTTP 4" not in str(e):
            raise
        return chat(model, [{"role": "user", "content": f'{prompt} <img src="{url}" />'}],
                    temperature=0.2, max_tokens=2000)
