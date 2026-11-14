# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""İşlem defteri ve geri alma (v1.4)."""
import os
import time

import pytest

from modules import functions as fx
from modules import islem_defteri as DEF


@pytest.fixture
def ev(tmp_path, monkeypatch):
    """Kullanıcı klasörü test klasörünün içinde (FENIX çöp kutusuyla aynı sürücü)."""
    home = tmp_path / "ev"
    (home / "Desktop").mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(fx, "resolve_folders", lambda name: [str(home / "Desktop")])
    return home


def test_yeni_dosya_deftere_yazilir_ve_geri_alinir(ev):
    r = fx.write_file("liste.txt", "süt\nekmek")
    assert r["status"] == "ok"
    yol = r["yol"]
    k = DEF.son_geri_alinabilir()
    assert k["tur"] == "olusturma" and k["yol"] == yol
    g = DEF.geri_al()
    assert g["status"] == "ok" and not os.path.exists(yol)
    assert DEF.son_geri_alinabilir() is None                      # aynı işlem iki kez geri alınmaz
    assert "geri alındı" in DEF.ozet_metni()


def test_uzerine_yazma_geri_alininca_eski_hal_doner(ev):
    yol = fx.write_file("not.txt", "eski")["yol"]
    fx.write_file("not.txt", "yeni", overwrite=True)
    assert open(yol, encoding="utf-8").read().endswith("yeni")
    assert DEF.geri_al()["status"] == "ok"
    assert open(yol, encoding="utf-8").read().endswith("eski")


def test_duzenleme_geri_alinir(ev):
    yol = fx.write_file("kod.txt", "a = 1\nb = 2\n")["yol"]
    os.makedirs("data", exist_ok=True)
    assert fx.edit_file(yol, "b = 2", "b = 3")["status"] == "ok"
    assert "b = 3" in open(yol, encoding="utf-8").read()
    assert DEF.son_geri_alinabilir()["tur"] == "duzenleme"
    assert DEF.geri_al()["status"] == "ok"
    assert "b = 2" in open(yol, encoding="utf-8").read()


def test_silinen_dosya_copten_yerine_doner(ev):
    yol = ev / "Desktop" / "odev.docx"
    yol.write_bytes(b"icerik")
    cop = DEF.cope_tasi(str(yol))
    DEF.kaydet("silme", "odev.docx", str(yol), {"islem": "copten_geri", "cop": cop, "yol": str(yol)})
    assert not yol.exists() and os.path.exists(cop)
    assert DEF.geri_al()["status"] == "ok"
    assert yol.read_bytes() == b"icerik"


def test_geri_alma_var_olan_dosyanin_uzerine_yazmaz(ev):
    yol = ev / "Desktop" / "a.txt"
    yol.write_text("ilk")
    cop = DEF.cope_tasi(str(yol))
    DEF.kaydet("silme", "a.txt", str(yol), {"islem": "copten_geri", "cop": cop, "yol": str(yol)})
    yol.write_text("kullanıcının yeni dosyası")
    r = DEF.geri_al()
    assert r["status"] == "error" and yol.read_text() == "kullanıcının yeni dosyası"


def test_onay_verilmezse_geri_alinmaz(ev):
    yol = fx.write_file("x.txt", "1")["yol"]
    r = DEF.geri_al(onayla=lambda *a: False)
    assert r["status"] == "cancelled" and os.path.exists(yol)


def test_numara_ile_geri_alma(ev):
    fx.write_file("bir.txt", "1")
    ilk = DEF.son_geri_alinabilir()["id"]
    fx.write_file("iki.txt", "2")
    assert DEF.geri_al(ilk)["status"] == "ok"
    assert not os.path.exists(ev / "Desktop" / "bir.txt") and os.path.exists(ev / "Desktop" / "iki.txt")


def test_cop_30_gunden_eskileri_siler():
    os.makedirs(os.path.join(DEF.COP, f"{int(time.time()) - 31 * 86400}_eski"))
    os.makedirs(os.path.join(DEF.COP, f"{int(time.time()) - 5 * 86400}_yeni"))
    assert DEF.cop_temizle() == 1
    assert sorted(os.listdir(DEF.COP)) == [n for n in sorted(os.listdir(DEF.COP)) if n.endswith("_yeni")]


def test_komut_deftere_yazilir_ama_geri_alinamaz(monkeypatch):
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(fx, "_exec_ps", lambda c, *a, **k: {"status": "ok", "message": ""})
    fx.run_command("Get-Date", "Saati göster")
    k = DEF.oku()[-1]
    assert k["tur"] == "komut" and k["geri"] is None
    assert "geri alınamaz" in DEF.ozet_metni()


def test_bos_defter():
    assert "değişiklik yapmadım" in DEF.ozet_metni()
    assert DEF.geri_al()["status"] == "error"


@pytest.mark.parametrize("metin,beklenen", [
    ("bugün ne yaptın?", True), ("Bugün neler yaptın", True), ("işlem defterini göster", True),
    ("bugün hava nasıl", False), ("dün ne yaptın", False)])
def test_ne_yaptin_algilama(metin, beklenen):
    from modules.agent import NE_YAPTIN_RE
    assert bool(NE_YAPTIN_RE.search(metin)) == beklenen


@pytest.mark.parametrize("metin,id_", [
    ("geri al", None), ("son yaptığını geri al", None), ("Son işlemi geri al.", None),
    ("geri alır mısın?", None), ("a1b2c3d4 geri al", "a1b2c3d4"), ("a1b2c3d4 numaralı işlemi geri al", "a1b2c3d4")])
def test_geri_al_algilama(metin, id_):
    from modules.agent import GERI_AL_RE
    m = GERI_AL_RE.match(metin)
    assert m and m.group("id") == id_


@pytest.mark.parametrize("metin", ["dosyayı geri alıp masaüstüne koy ve sonra bana rapor yaz", "geri alma tuşu nerede"])
def test_uzun_ya_da_farkli_cumleler_geri_al_sayilmaz(metin):
    from modules.agent import GERI_AL_RE
    assert not GERI_AL_RE.match(metin)
