# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""FENIX otomatik testleri — ortak ayarlar.

Testler GERÇEK verine dokunmaz: her test geçici bir klasörde çalışır (data/ orada oluşur), internete çıkmaz,
konuşmaz, onay kutusu açmaz, PowerShell komutu çalıştırmaz. API anahtarı gerekmez.
Çalıştırma: Calistir_Testler.bat  (ya da: venv\\Scripts\\python.exe -m pytest tests)"""
import os
import socket
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def izole(tmp_path, monkeypatch):
    """Her test kendi boş klasöründe: data/... yolları geçici klasöre gider, gerçek hafıza etkilenmez."""
    monkeypatch.chdir(tmp_path)
    from modules import functions as fx
    monkeypatch.setattr(fx, "_speak", lambda *a, **k: None)
    monkeypatch.setattr(fx, "_SPEAK_REAL", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(fx, "_notify", lambda *a, **k: None)

    def _no_ps(*a, **k):
        raise AssertionError("Test sırasında PowerShell komutu çalıştırılmaya çalışıldı")
    monkeypatch.setattr(fx, "_exec_ps", _no_ps)

    gercek_connect, gercek_create = socket.socket.connect, socket.create_connection

    def _yerel(adres):
        host = adres[0] if isinstance(adres, tuple) else adres
        return host in ("127.0.0.1", "::1", "localhost") or not isinstance(adres, tuple)

    def _connect(self, adres):          # yalnızca bilgisayarın kendisine (Windows'ta asyncio bunu kullanır) izin var
        if not _yerel(adres):
            raise AssertionError("Test sırasında internete çıkılmaya çalışıldı")
        return gercek_connect(self, adres)

    def _create(adres, *a, **k):
        if not _yerel(adres):
            raise AssertionError("Test sırasında internete çıkılmaya çalışıldı")
        return gercek_create(adres, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", _connect)
    monkeypatch.setattr(socket, "create_connection", _create)
    yield tmp_path


@pytest.fixture
def ayar():
    """config.example.yaml (anahtarsız örnek ayar dosyası)."""
    import yaml
    with open(os.path.join(ROOT, "config.example.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)
