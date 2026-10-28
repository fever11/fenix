# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
FENIX Bağlantı Testi
---------------------
config.yaml'daki anahtarlarla her servisi tek tek dener ve sonucu açıkça yazar:
Gemini (metin), Gemini (görüntü = ekran görme), Gemini embedding (hafıza), Groq, Groq Whisper, Tavily.
Çalıştırma: Connection_Test.bat (çift tıkla)
"""
import io
import sys
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
keys = cfg.get("api_keys", {})
gem = (keys.get("gemini") or "").strip()
groq = (keys.get("groq") or "").strip()
tav = (keys.get("tavily") or "").strip()
models = [cfg["modes"][m].get("gemini_model") for m in ("safe", "normal", "devil")] + (cfg.get("gemini_fallbacks") or [])
models = list(dict.fromkeys(m for m in models if m))


def show(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  —  {detail}" if detail else ""))


def short(e):
    t = str(e).replace("\n", " ")
    if "429" in t or "RESOURCE_EXHAUSTED" in t:
        return "KOTA DOLMUŞ (429) — yarın sıfırlanır ya da faturalandırma aç"
    if "404" in t or "NOT_FOUND" in t:
        return "MODEL BULUNAMADI (404) — config.yaml'daki model adını değiştir"
    if "API key" in t or "401" in t or "403" in t or "PERMISSION" in t or "invalid" in t.lower():
        return "ANAHTAR GEÇERSİZ — config.yaml'daki anahtarı kontrol et"
    return t[:160]


print("=" * 64)
print(" FENIX BAĞLANTI TESTİ")
print("=" * 64)

print("\nGEMINI (ekran görme ve hafıza için gerekli)")
if not gem or gem.startswith("BURAYA"):
    show("Gemini anahtarı", False, "config.yaml'da girilmemiş")
else:
    from google import genai
    from google.genai import types
    from PIL import Image
    client = genai.Client(api_key=gem)
    img = Image.new("RGB", (220, 60), (255, 255, 255))
    try:
        from PIL import ImageDraw
        ImageDraw.Draw(img).text((10, 20), "FENIX TEST 42", fill=(0, 0, 0))
    except Exception:
        pass
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    for m in models:
        try:
            r = client.models.generate_content(model=m, contents="Sadece 'tamam' yaz.")
            show(f"{m} (metin)", True, (r.text or "").strip()[:30])
        except Exception as e:
            show(f"{m} (metin)", False, short(e))
            continue
        try:
            r = client.models.generate_content(model=m, contents=[
                types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                types.Part.from_text(text="Görselde yazan metni aynen yaz.")])
            show(f"{m} (görüntü / ekran görme)", True, (r.text or "").strip()[:40])
        except Exception as e:
            show(f"{m} (görüntü / ekran görme)", False, short(e))
    try:
        client.models.embed_content(model="gemini-embedding-001", contents=["test"],
                                    config=types.EmbedContentConfig(output_dimensionality=768))
        show("gemini-embedding-001 (hafıza)", True)
    except Exception as e:
        show("gemini-embedding-001 (hafıza)", False, short(e))

print("\nGROQ (sohbet, PC kontrolü, ses tanıma)")
if not groq:
    show("Groq anahtarı", False, "config.yaml'da girilmemiş (her şey Gemini'ye düşer)")
else:
    import requests
    h = {"Authorization": f"Bearer {groq}"}
    for m in dict.fromkeys([cfg["modes"]["normal"].get("groq_model"), cfg["modes"]["safe"].get("groq_model")]):
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=h, timeout=30,
                              json={"model": m, "messages": [{"role": "user", "content": "Sadece 'tamam' yaz."}]})
            ok = r.status_code == 200
            show(f"{m}", ok, "" if ok else f"{r.status_code}: {r.text[:140]}")
        except Exception as e:
            show(f"{m}", False, short(e))
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers=h, timeout=30)
        ids = {d["id"] for d in r.json().get("data", [])} if r.status_code == 200 else set()
        stt = cfg.get("audio", {}).get("stt_model", "whisper-large-v3-turbo")
        show(f"{stt} (ses tanıma)", stt in ids, "" if stt in ids else "Groq listesinde yok; yedek model denenecek")
    except Exception as e:
        show("Groq model listesi", False, short(e))

print("\nNVIDIA (Groq dolunca yedek sohbet, isteğe bağlı)")
nv = ((cfg.get("api_keys") or {}).get("nvidia") or "").strip()
if not nv or nv.startswith("BURAYA"):
    show("NVIDIA anahtarı", False, "girilmemiş (Groq dolunca doğrudan Gemini kullanılır)")
else:
    import requests
    nmodels = ((cfg.get("nvidia") or {}).get("chat_models") or [])[:2]
    for m in nmodels:
        try:
            r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", timeout=120,
                              headers={"Authorization": f"Bearer {nv}"},
                              json={"model": m, "max_tokens": 20, "messages": [{"role": "user", "content": "Sadece 'tamam' yaz."}]})
            ok = r.status_code == 200
            show(f"{m}", ok, "" if ok else f"{r.status_code}: {r.text[:140]}")
        except Exception as e:
            show(f"{m}", False, short(e))

print("\nTAVILY (web araması, isteğe bağlı)")
if not tav:
    show("Tavily anahtarı", False, "girilmemiş (DuckDuckGo/Bing kullanılır)")
else:
    import requests
    try:
        r = requests.post("https://api.tavily.com/search", timeout=30,
                          json={"api_key": tav, "query": "FENIX test", "max_results": 1})
        show("Tavily arama", r.status_code == 200, "" if r.status_code == 200 else f"{r.status_code}: {r.text[:120]}")
    except Exception as e:
        show("Tavily arama", False, short(e))

print("\nNot: '✗ ... görüntü' satırı varsa FENIX ekranı ve yapıştırılan görselleri o yüzden göremiyor.")
input("\nKapatmak için Enter...")
