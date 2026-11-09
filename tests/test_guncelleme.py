# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Güncelleme bildirimi: sadece resmi depodaki yeni SÜRÜM bildirilir; hiçbir şey indirilmez/çalıştırılmaz."""
import pytest
from modules import guncelleme as g, user_settings


def _surum(etiket, **ek):
    return dict({"tag_name": etiket, "name": f"FENIX {etiket}", "html_url": f"https://github.com/fever11/fenix/releases/tag/{etiket}",
                 "body": "## Yenilikler\n- Güncelleme bildirimi\n- Hız iyileştirmesi", "draft": False, "prerelease": False}, **ek)


def test_surum_karsilastirma():
    assert g.daha_yeni_mi("v1.2.10", "1.2.9") and g.daha_yeni_mi("v2.0", "1.9.9")
    assert not g.daha_yeni_mi("v1.2.1", "1.2.1") and not g.daha_yeni_mi("v1.0.0", "1.2.1")
    assert not g.daha_yeni_mi("son-surum", "1.2.1")


def test_yeni_surum_bulunur_ve_ozetlenir():
    b = g.denetle(zorla=True, getir=lambda url: _surum("v9.0.0"))
    assert b["surum"] == "9.0.0" and "Güncelleme bildirimi" in b["ozet"] and "#" not in b["ozet"]
    assert b["sayfa"].startswith("https://github.com/fever11/fenix/")


def test_eski_ayni_taslak_on_surum_bildirilmez():
    for v in (_surum("v1.0.0"), _surum(g.VERSION), _surum("v9.0.0", draft=True), _surum("v9.0.0", prerelease=True)):
        assert g.denetle(zorla=True, getir=lambda url, v=v: v) is None


def test_baska_siteye_yonlendirme_yapilmaz():
    b = g.denetle(zorla=True, getir=lambda url: _surum("v9.0.0", html_url="https://kotu-site.example/indir.exe"))
    assert b["sayfa"] == g.RESMI_SAYFA
    assert not g.guvenli_adres("https://github.com/baskasi/fenix/releases")


def test_atlanan_surum_bir_daha_bildirilmez_yenisi_bildirilir():
    g.atla("v9.0.0")
    assert g.denetle(zorla=True, getir=lambda url: _surum("v9.0.0")) is None
    assert g.denetle(zorla=True, getir=lambda url: _surum("v9.1.0"))["etiket"] == "v9.1.0"


def test_ag_hatasi_sessiz_ve_6_saat_sinir():
    def hata(url):
        raise OSError("ağ yok")
    assert g.denetle(zorla=True, getir=hata) is None
    sayac = {"n": 0}

    def say(url):
        sayac["n"] += 1
        return _surum("v9.0.0")
    g.denetle(getir=say)                       # az önce denetlendi (hata da olsa): 6 saat dolmadan istek atılmaz
    assert sayac["n"] == 0


def test_ayarlardan_kapatilabilir():
    user_settings.set("guncelleme_denetle", False)
    assert g.denetle(getir=lambda url: pytest.fail("kapalıyken istek atıldı")) is None
