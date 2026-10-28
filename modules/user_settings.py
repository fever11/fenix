# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Kullanıcının sohbetten değiştirdiği kalıcı ayarlar (ör. ses hızı/tonu).
config.yaml'a dokunulmaz; data/ayarlar.json dosyasında tutulur."""
import os
import json
import threading

PATH = os.path.join("data", "ayarlar.json")
_LOCK = threading.Lock()


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get(key, default=None):
    return _load().get(key, default)


def set(key, value):
    with _LOCK:
        data = _load()
        data[key] = value
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
