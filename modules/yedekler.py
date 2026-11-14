# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Ek yedek sağlayıcılar (v1.4). Groq'un kotası dolunca yavaş NVIDIA'dan ÖNCE denenir.

Hepsi OpenAI uyumlu API kullanır; tek kodla bağlanır. config.yaml'da api_keys altına anahtarı yazılan sağlayıcı
kullanılır, yazılmayan atlanır (anahtar yoksa FENIX eskisi gibi çalışır):
  api_keys:
    cloudflare: "..."           # Workers AI API token (günde 10.000 nöron ≈ 50 soru; Groq'taki aynı gpt-oss-120b)
    cloudflare_hesap: "..."     # Cloudflare Account ID (adres çubuğundaki uzun kod)
    openrouter: "..."           # https://openrouter.ai/keys  (ücretsiz modeller; günde 50 istek)
    cohere: "..."               # https://dashboard.cohere.com  (deneme anahtarı; ayda 1.000 istek, ticari değil)
    mistral: "..."              # API için ücretli plan gerekir (14.11.2026)
    sambanova: "..."            # ödeme yöntemi gerekir (14.11.2026'da kartsız hesapta 402 döndü)
Sıra ve modeller isteğe bağlı olarak değiştirilebilir:
  yedekler:
    sira: [cloudflare, openrouter, cohere, mistral, sambanova]
    mistral: {modeller: ["mistral-small-latest"]}

Gemini'ye dokunulmaz (kotası ekran okumaya ayrılmış). Kotası dolan/hata veren sağlayıcı bir süre dinlendirilir ki
her soruda yeniden denenip zaman kaybettirmesin.
"""
import hashlib
import time

HAZIR = {
    # URL'deki {hesap}: api_keys.<ad>_hesap değeriyle doldurulur (Cloudflare Account ID)
    # Workers AI cevap uzunluğu belirtilmezse kısa kesiyor (14.11: "…Öğle saat" diye yarıda kaldı); gpt-oss düşünme
    # adımları da bu sınırdan yer.
    "cloudflare": {"ad": "Cloudflare", "url": "https://api.cloudflare.com/client/v4/accounts/{hesap}/ai/v1/chat/completions",
                   "modeller": ["@cf/openai/gpt-oss-120b", "@cf/openai/gpt-oss-20b"], "hesap_gerekir": True,
                   "max_tokens": 4096},
    "cohere": {"ad": "Cohere", "url": "https://api.cohere.ai/compatibility/v1/chat/completions",
               "modeller": ["command-a-03-2025"]},
    "mistral": {"ad": "Mistral", "url": "https://api.mistral.ai/v1/chat/completions",
                "modeller": ["mistral-small-latest"], "mistral_uyumu": True},
    "sambanova": {"ad": "SambaNova", "url": "https://api.sambanova.ai/v1/chat/completions",
                  "modeller": ["gpt-oss-120b"]},
    "openrouter": {"ad": "OpenRouter", "url": "https://openrouter.ai/api/v1/chat/completions",
                   # 14.11: 'openai/gpt-oss-120b:free' artık yok (404). openrouter/free, isteğin gerektirdiği
                   # özellikleri (araç çağırma) destekleyen ücretsiz bir modeli kendisi seçer.
                   "modeller": ["openrouter/free", "google/gemma-4-31b-it:free"]},
}
VARSAYILAN_SIRA = ["cloudflare", "openrouter", "cohere", "mistral", "sambanova"]
DINLENME_SN = 10 * 60          # hata/kota sonrası bu süre denenmez
GUNLUK_DINLENME_SN = 3 * 3600  # günlük sınır dolunca

_AKTIF = {}                    # ad -> {ad, url, anahtar, modeller, mistral_uyumu}
_SIRA = []
_DINLEN = {}                   # ad -> zaman


def configure(cfg):
    _AKTIF.clear()
    _SIRA.clear()
    anahtarlar = (cfg or {}).get("api_keys") or {}
    ayar = (cfg or {}).get("yedekler") or {}
    sira = [s for s in (ayar.get("sira") or VARSAYILAN_SIRA) if s in HAZIR]
    for ad in sira:
        anahtar = str(anahtarlar.get(ad) or "").strip()
        if not anahtar or anahtar.upper().startswith("BURAYA"):
            continue
        p = dict(HAZIR[ad])
        if p.get("hesap_gerekir"):
            hesap = str(anahtarlar.get(f"{ad}_hesap") or "").strip()
            if not hesap or hesap.upper().startswith("BURAYA"):
                print(f"[YEDEK] {p['ad']}: anahtar var ama hesap numarası ({ad}_hesap) yok; atlanıyor")
                continue
            p["url"] = p["url"].replace("{hesap}", hesap)
        ozel = ayar.get(ad) or {}
        modeller = [m.strip() for m in (ozel.get("modeller") or []) if isinstance(m, str) and m.strip()]
        if modeller:
            p["modeller"] = modeller
        p["anahtar"] = anahtar
        _AKTIF[ad] = p
        _SIRA.append(ad)


def sira():
    """Şu an kullanılabilir (anahtarı olan, dinlenmeyen) yedekler."""
    simdi = time.time()
    return [a for a in _SIRA if _DINLEN.get(a, 0) <= simdi]


def bilgi(ad):
    return _AKTIF.get(ad)


def dinlendir(ad, gunluk=False):
    _DINLEN[ad] = time.time() + (GUNLUK_DINLENME_SN if gunluk else DINLENME_SN)


def _kisa_id(eski):
    """Mistral araç çağrısı kimliği 9 harf/rakam olmalı; Groq'un ürettiği kimlikler tutarlı biçimde çevrilir."""
    return hashlib.sha1(str(eski).encode()).hexdigest()[:9]


def uyarla(ad, payload):
    """Sağlayıcıya özel küçük farklar. Cevap uzunluğu sınırı (Cloudflare). Mistral: sistem mesajı sadece başta
    olabilir, araç kimlikleri 9 karakter, belirli bir aracı zorlamak yerine 'any'."""
    p = _AKTIF.get(ad) or HAZIR.get(ad) or {}
    if p.get("max_tokens") and "max_tokens" not in payload:
        payload = dict(payload, max_tokens=p["max_tokens"])
    if not p.get("mistral_uyumu"):
        return payload
    out = dict(payload)
    mesajlar, notlar = [], []
    for i, m in enumerate(payload.get("messages") or []):
        m = dict(m)
        if m.get("role") == "system" and i > 0:
            # Ara sistem notları baştaki talimata eklenir ('tool' rolünden sonra 'user' gelmesini de reddediyor)
            notlar.append(str(m.get("content") or ""))
            continue
        if m.get("tool_calls"):
            m["tool_calls"] = [dict(c, id=_kisa_id(c.get("id"))) for c in m["tool_calls"]]
        if m.get("role") == "tool" and m.get("tool_call_id"):
            m["tool_call_id"] = _kisa_id(m["tool_call_id"])
        mesajlar.append(m)
    if notlar and mesajlar and mesajlar[0].get("role") == "system":
        mesajlar[0] = dict(mesajlar[0], content=str(mesajlar[0].get("content") or "") + "\n\n" + "\n".join(notlar))
    out["messages"] = mesajlar
    if isinstance(out.get("tool_choice"), dict):
        out["tool_choice"] = "any"
    return out
