# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Eklentiler (MCP): şema temizleme, araç adları ve sahte bir MCP sunucusuyla uçtan uca güvenlik kuralları."""
import os
import sys
import time

import pytest

from modules import functions as fx
from modules import mcp_eklenti as mx


def test_sema_gemini_ve_groq_icin_sadelesir():
    s = mx.sema_temizle({"$schema": "x", "type": "object", "additionalProperties": False,
                         "properties": {"yol": {"type": ["string", "null"], "default": "a"},
                                        "adet": {"anyOf": [{"type": "integer"}, {"type": "null"}], "description": "kaç"},
                                        "liste": {"type": "array"}},
                         "required": ["yol", "olmayan"]})
    assert s == {"type": "object", "required": ["yol"],
                 "properties": {"yol": {"type": "string"}, "adet": {"type": "integer", "description": "kaç"},
                                "liste": {"type": "array", "items": {"type": "string"}}}}


def test_arac_adi_gecerli_ve_kisa():
    ad = mx.arac_adi("dosyalar", "list-directory.with sizes" + "x" * 80)
    assert ad.startswith("mcp_dosyalar_list_directory_with_sizes") and len(ad) <= 64


def test_ayar_yoksa_hazir_liste_false_ise_hic():
    assert [e["ad"] for e in mx.ayarlar({})] == ["zaman", "git", "dosyalar"]
    assert mx.ayarlar({"eklentiler": False}) == []
    assert mx.ayarlar({"eklentiler": [{"ad": "a", "komut": "x", "aktif": False}]}) == []


def test_anahtar_ayardan_okunur():
    o = mx.ortam_coz({"TAVILY_API_KEY": "{anahtar:tavily}", "SABIT": "1", "YOK": "{anahtar:olmayan}"},
                     {"tavily": "tvly-xyz"})
    assert o == {"TAVILY_API_KEY": "tvly-xyz", "SABIT": "1", "YOK": ""}


@pytest.fixture
def sahte_eklenti(monkeypatch):
    pytest.importorskip("mcp")
    mx._STATE.update(loop=None, thread=None, servers={}, mesaj="", basladi=False)
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahte_mcp_sunucu.py")
    mx.baslat({"eklentiler": [{"ad": "sahte", "komut": [sys.executable, yol]}]})
    for _ in range(300):
        s = mx._STATE["servers"].get("sahte")
        if s and s.durum != "başlatılıyor":
            break
        time.sleep(0.1)
    s = mx._STATE["servers"]["sahte"]
    assert s.durum == "hazır", s.hata
    yield s
    mx.durdur()
    time.sleep(0.3)
    mx._STATE.update(servers={}, basladi=False)


def test_eklenti_araclari_fenixe_eklenir(sahte_eklenti):
    assert "mcp_sahte_selamla" in fx.WHITELISTED_FUNCTIONS and "mcp_sahte_sil" in fx.WHITELISTED_FUNCTIONS
    assert "mcp_sahte_selamla" in fx.READONLY_FUNCTIONS          # salt okunur: Güvenli modda da kullanılabilir
    assert "mcp_sahte_sil" not in fx.READONLY_FUNCTIONS          # silme: Güvenli modda yok
    assert any(s["name"] == "mcp_sahte_sil" for s in fx.FUNCTION_SCHEMAS)


def test_salt_okunur_arac_onaysiz_calisir(sahte_eklenti, monkeypatch):
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: pytest.fail("Salt okunur araç onay sordu"))
    r = fx.WHITELISTED_FUNCTIONS["mcp_sahte_selamla"](isim="Mustafa")
    assert r == {"status": "ok", "message": "Merhaba Mustafa"}


def test_silme_araci_onaysiz_calismaz(sahte_eklenti, monkeypatch):
    sorulan = []
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: sorulan.append(a) or False)
    r = fx.WHITELISTED_FUNCTIONS["mcp_sahte_sil"](yol="C:/onemli.txt")
    assert sorulan and "SİLME" in sorulan[0][0]
    assert r["status"] == "cancelled"


def test_silme_araci_onaylaninca_calisir(sahte_eklenti, monkeypatch):
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: True)
    assert fx.WHITELISTED_FUNCTIONS["mcp_sahte_sil"](yol="a.txt")["message"] == "SILINDI:a.txt"


def test_eklenti_kapaninca_araclari_kaldirilir(sahte_eklenti):
    mx.durdur()
    for _ in range(50):
        if "mcp_sahte_sil" not in fx.WHITELISTED_FUNCTIONS:
            break
        time.sleep(0.1)
    assert "mcp_sahte_sil" not in fx.WHITELISTED_FUNCTIONS
    assert not any(s["name"].startswith("mcp_sahte_") for s in fx.FUNCTION_SCHEMAS)


def test_bozuk_eklenti_fenixi_durdurmaz():
    pytest.importorskip("mcp")
    mx._STATE.update(loop=None, thread=None, servers={}, mesaj="", basladi=False)
    mx.baslat({"eklentiler": [{"ad": "bozuk", "komut": ["olmayan_program_xyz"]}]})
    for _ in range(100):
        s = mx._STATE["servers"].get("bozuk")
        if s and s.durum != "başlatılıyor":
            break
        time.sleep(0.1)
    assert mx._STATE["servers"]["bozuk"].durum == "hata"
    assert "bozuk" in mx.durum_metni()
    mx.durdur()
    mx._STATE.update(servers={}, basladi=False)


def test_pencere_secimleri_ayarlardan_once_gelir():
    cfg = {"eklentiler": [{"ad": "zaman", "komut": ["x"]}, {"ad": "notion", "komut": ["y"], "aktif": False}]}
    assert [e["ad"] for e in mx.ayarlar(cfg)] == ["zaman"]
    mx.secim_kaydet({"zaman": False, "notion": True, "tarayici": True})
    calisan = [e["ad"] for e in mx.ayarlar(cfg)]
    assert calisan == ["notion", "tarayici"]          # tarayıcı katalogdan eklendi, zaman kapatıldı
    satirlar = {e["ad"]: e for e in mx.liste(cfg)}
    assert satirlar["notion"]["kaynak"] == "ayar" and satirlar["tarayici"]["kaynak"] == "katalog"
    assert set(satirlar) >= {"zaman", "git", "dosyalar", "tarayici", "tavily", "notion", "github"}


def test_anahtar_eksigi_gorunur():
    notion = next(k for k in mx.KATALOG if k["ad"] == "notion")
    assert "anahtar girilmemiş" in mx.eksikler(notion, {"api_keys": {}})
    assert "anahtar girilmemiş" not in mx.eksikler(notion, {"api_keys": {"notion": "ntn_x"}})


def test_anahtar_kaydi_diger_ayarlari_bozmaz():
    import ast
    import os
    kaynak = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"),
                  encoding="utf-8").read()
    agac = ast.parse(kaynak)
    fn = next(n for n in agac.body if isinstance(n, ast.FunctionDef) and n.name == "_put_key")
    ns = {"re": __import__("re")}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "app.py", "exec"), ns)
    metin = 'api_keys:\n  gemini: "AAA"  # yorum\n  groq: ""\nmodes:\n  safe: {}\n'
    yeni = ns["_put_key"](ns["_put_key"](metin, "notion", "ntn_123"), "groq", "gsk_9")
    assert 'notion: "ntn_123"' in yeni and 'groq: "gsk_9"' in yeni and 'gemini: "AAA"  # yorum' in yeni
    assert yeni.count("api_keys:") == 1 and "modes:" in yeni


def test_kendi_eklentini_ekle_ve_sil():
    ok, ad = mx.ozel_ekle("Spotify", "npx -y @someone/spotify-mcp", "SPOTIFY_TOKEN")
    assert ok and ad == "spotify"
    e = next(x for x in mx.liste({}) if x["ad"] == "spotify")
    assert e["komut"] == ["npx", "-y", "@someone/spotify-mcp"] and e["onay"] == "her_zaman"
    assert e["ortam"] == {"SPOTIFY_TOKEN": "{anahtar:spotify}"} and e["anahtar"] == "spotify"
    assert any(x["ad"] == "spotify" for x in mx.ayarlar({}))
    mx.ozel_sil("spotify")
    assert not any(x["ad"] == "spotify" for x in mx.liste({}))


@pytest.mark.parametrize("paket", ["paket; rm -rf /", "a && calc", "../evil", "", "Paket Adı"])
def test_tehlikeli_paket_adi_reddedilir(paket):
    ok, msg = mx.ozel_ekle("x", paket)
    assert not ok


def test_katalog_adi_kullanilamaz():
    assert not mx.ozel_ekle("notion", "foo")[0]
