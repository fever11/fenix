# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Kısayol Komutları (tek cümleyle birden çok iş)
---------------------------------------------
"çalışma modu" -> ["VS Code'u aç", "Spotify'ı aç", "masaüstündeki fenix klasörünü aç"]
Kısayollar data/kisayollar.json dosyasında tutulur. FENIX'e sohbetten kaydettirilir:
  "çalışma modu dediğimde VS Code'u, Spotify'ı ve proje klasörünü aç"
Sonra sadece "çalışma modu" (ya da "çalışma modunu aç / başlat") demek yeterli.
"""
import os
import re
import json

PATH = os.path.join("data", "kisayollar.json")
FILLER = {"aç", "ac", "başlat", "baslat", "çalıştır", "calistir", "yap", "modunu", "modu", "moduna", "geç", "gec",
          "lütfen", "lutfen", "hadi", "şimdi", "simdi", "kısayolunu", "kısayolu", "kisayolu", "kisayolunu"}


def _norm(t):
    t = (t or "").lower().replace("’", "'")
    t = re.sub(r"[^\wçğıöşü\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load():
    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: [s for s in v if isinstance(s, str) and s.strip()] for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def _save(data):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save(name, steps):
    name = _norm(name)
    steps = [s.strip() for s in steps if isinstance(s, str) and s.strip()][:12]
    if not name or not steps:
        raise ValueError("Kısayolun bir adı ve en az bir adımı olmalı.")
    data = load()
    data[name] = steps
    _save(data)
    return name, steps


def delete(name):
    data = load()
    key = _norm(name)
    if key in data:
        del data[key]
        _save(data)
        return True
    return False


def match(text):
    """Mesaj bir kısayolu çalıştırma isteği mi? (ad, adımlar) ya da None.
    'çalışma modu', 'çalışma modunu aç', 'çalışma modunu başlat lütfen' eşleşir; içinde başka bir istek
    olan cümleler (ör. 'çalışma modu kısayolunu değiştir') eşleşmez."""
    t = _norm(text)
    if not t:
        return None
    data = load()
    for name in sorted(data, key=len, reverse=True):
        if t == name:
            return name, data[name]
        name_words = name.split()
        words = t.split()
        # ad + yalnızca dolgu kelimeleri ('modunu aç' vb.); son kelimenin ekli hali de kabul
        if len(words) >= len(name_words):
            head = words[:len(name_words)]
            ok_head = all(w == n or (i == len(name_words) - 1 and w.startswith(n[:max(3, len(n) - 1)]))
                          for i, (w, n) in enumerate(zip(head, name_words)))
            if ok_head and all(w in FILLER for w in words[len(name_words):]):
                return name, data[name]
    return None
