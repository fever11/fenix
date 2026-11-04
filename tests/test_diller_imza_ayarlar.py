# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Çeviri dosyaları, imza, örnek ayar dosyası ve gizlilik kuralları (.gitignore)."""
import glob
import json
import os
import re

import pytest

from conftest import ROOT

DILLER = ["en", "de", "ru", "fr", "es"]


def sozluk(dil):
    with open(os.path.join(ROOT, "locales", f"{dil}.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("dil", DILLER)
def test_ceviri_dosyasi_gecerli_ve_bolumleri_var(dil):
    d = sozluk(dil)
    assert set(d) >= {"strings", "templates", "tools"}
    assert all(isinstance(v, str) and v.strip() for v in d["strings"].values())


@pytest.mark.parametrize("dil", DILLER[1:])
def test_her_dil_ingilizceyle_ayni_metinleri_cevirir(dil):
    en, d = sozluk("en"), sozluk(dil)
    for bolum in ("strings", "templates", "tools"):
        eksik = set(en[bolum]) - set(d[bolum])
        assert not eksik, f"{dil}.json/{bolum} içinde eksik çeviri: {sorted(eksik)[:5]}"


@pytest.mark.parametrize("dil", DILLER)
def test_sablonlarda_yer_tutucu_sayisi_korunur(dil):
    yer = re.compile(r"\{\d*\}")          # {} ya da sıralı {0} {1} (dile göre sıra değişebilir)
    for kaynak, ceviri in sozluk(dil)["templates"].items():
        assert len(yer.findall(kaynak)) == len(yer.findall(ceviri)), f"{dil}: '{kaynak}' -> '{ceviri}'"


def test_arac_cevirileri_gercek_araclara_ait():
    from modules import functions as fx
    from modules import mcp_eklenti
    mcp_eklenti.install()
    ozel = {"lab_add_topic", "lab_status", "lab_forget"}      # yalnızca özel sürümde (öğrenme modu) eklenen araçlar
    fazla = set(sozluk("en")["tools"]) - set(fx.WHITELISTED_FUNCTIONS) - ozel
    assert not fazla, f"Olmayan araç için çeviri: {fazla}"


def test_ceviri_calisir():
    from modules import i18n
    i18n.set_language("en")
    try:
        assert i18n.tr("Salt okunur") == "Read-only"
        assert i18n.tr("Bu metin sözlükte yok") == "Bu metin sözlükte yok"     # yoksa Türkçe kalır
    finally:
        i18n.set_language("tr")


def test_imza_butun():
    from modules import imza
    assert imza.verify(), "İmza bozulmuş: sürüm etiketi 'unofficial build' gösterir"


def test_her_kaynak_dosyada_imza_satiri_var():
    dosyalar = [os.path.join(ROOT, "app.py")] + glob.glob(os.path.join(ROOT, "modules", "*.py"))
    eksik = []
    for p in dosyalar:
        if os.path.basename(p) == "__init__.py":
            continue
        with open(p, encoding="utf-8") as f:
            if "MK-Agentic-System" not in f.readline():
                eksik.append(os.path.basename(p))
    assert not eksik, f"İlk satırında imza olmayan dosyalar: {eksik}"


ANAHTAR_RE = re.compile(r"(gsk_[A-Za-z0-9]{20,}|nvapi-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|tvly-[A-Za-z0-9]{20,})")


def test_paylasilan_dosyalarda_gercek_api_anahtari_yok():
    bulunan = []
    for p in glob.glob(os.path.join(ROOT, "**", "*"), recursive=True):
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        if (os.path.isdir(p) or rel == "config.yaml" or rel.startswith(("data/", "venv/", ".venv/"))
                or "__pycache__" in rel or not rel.endswith((".py", ".yaml", ".yml", ".md", ".json", ".txt", ".bat",
                                                             ".ps1", ".vbs"))):
            continue
        with open(p, encoding="utf-8", errors="ignore") as f:
            if ANAHTAR_RE.search(f.read()):
                bulunan.append(rel)
    assert not bulunan, f"Gerçek API anahtarına benzeyen metin içeren dosyalar: {bulunan}"


def test_gizli_dosyalar_github_a_gitmez():
    with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
        satirlar = {s.strip() for s in f if s.strip() and not s.startswith("#")}
    for gerekli in ("config.yaml", "data/", "venv/"):
        assert gerekli in satirlar, f".gitignore'da {gerekli} yok"


def test_ornek_ayar_dosyasi_tutarli(ayar):
    assert ayar["default_mode"] in ayar["modes"]
    assert ayar["modes"]["safe"]["allow_actions"] is False, "Güvenli mod sisteme dokunabilir durumda!"
    for ad, anahtar in (ayar.get("api_keys") or {}).items():
        a = (anahtar or "").strip()
        assert not a or a.startswith("BURAYA_"), f"Örnek ayar dosyasında dolu anahtar var: {ad}"
