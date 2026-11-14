# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Sağ tık menüsü ve Numpad + kısayolu (v1.4)."""
import os
import time
import types

import pytest

from modules import sag_tik as S


def test_istek_kuyrugu_sirali_ve_tek_seferlik():
    S.istek_yaz("ozetle", yol="C:/a.txt")
    time.sleep(0.01)
    S.istek_yaz("metin", metin="merhaba dünya")
    al = S.istekleri_al()
    assert [k["eylem"] for k in al] == ["ozetle", "metin"]
    assert S.istekleri_al() == []                      # okunan istek silinir


def test_eski_istekler_atilir():
    k = S.istek_yaz("ozetle", yol="C:/a.txt")
    assert S.istekleri_al(en_eski_sn=-1) == []         # süresi geçmiş sayılır


def test_istek_metinleri():
    metin, ek, _ = S.istek_metni({"eylem": "ozetle", "yol": "C:/belge.docx"})
    assert "özetle" in metin and "C:/belge.docx" in metin and ek is None
    metin, ek, not_ = S.istek_metni({"eylem": "metin", "metin": "seçili  \n  yazı"})
    assert metin is None and ek == "seçili  \n  yazı" and "seçili yazı" in not_
    metin, ek, _ = S.istek_metni({"eylem": "sor", "yol": "C:/x.pdf"})
    assert metin is None and ek == "C:/x.pdf"


def test_klasor_ozetleme_klasor_metni_kullanir(tmp_path):
    metin, _, _ = S.istek_metni({"eylem": "ozetle", "yol": str(tmp_path)})
    assert "klasörde" in metin


def test_guvenlik_raporu_yapay_zeka_kullanmaz(tmp_path, monkeypatch):
    from modules import nobet
    f = tmp_path / "fatura.pdf.exe"
    f.write_bytes(b"MZ....")
    monkeypatch.setattr(nobet, "_defender_scan", lambda p: "temiz")
    monkeypatch.setattr(nobet, "_signature", lambda p: "Unsigned")
    r = S.guvenlik_raporu(str(f))
    assert "TEHLİKELİ" in r and "çift uzantı" in r and "%100 garanti değildir" in r


def test_guvenlik_raporu_dosya_yoksa():
    assert "bulunamadı" in S.guvenlik_raporu("C:/olmayan/dosya.txt")


def test_kayit_defteri_anahtarlari():
    a = dict(S.anahtarlar())
    ana = r"Software\Classes\*\shell\FENIX"
    assert a[ana]["SubCommands"] == "" and a[ana]["MUIVerb"] == "FENIX"
    komutlar = [v[""] for k, v in a.items() if k.endswith(r"\command")]
    assert any("--sor ozetle" in c and '"%1"' in c and "nobet_main.py" in c for c in komutlar)
    assert any(k.startswith(r"Software\Classes\Directory\shell\FENIX") for k in a)
    assert all(k.startswith("Software\\Classes\\") for k in a)      # sadece bu kullanıcı (HKCU), yönetici gerekmez


class _Ev:
    def __init__(self, tur, kod=S.NUMPAD_ARTI):
        self.event_type, self.scan_code = tur, kod


def test_numpad_kisa_basis_arti_yazar(monkeypatch):
    yazilan, gonderilen = [], []
    d = S.NumpadDinleyici(gonder=gonderilen.append, sure=0.3, tus="numpad_arti")
    monkeypatch.setattr(S.NumpadDinleyici, "_kisa_basis", lambda self: yazilan.append(self.karakter))
    assert d.olay(_Ev("down")) is False                 # tuş yutulur
    assert d.olay(_Ev("up")) is False
    time.sleep(0.05)
    assert yazilan == ["+"] and gonderilen == []


def test_numpad_uzun_basis_secili_metni_gonderir(monkeypatch):
    yazilan, gonderilen = [], []
    monkeypatch.setattr(S, "secili_metni_al", lambda: "seçili metin")
    monkeypatch.setattr(S.NumpadDinleyici, "_kisa_basis", lambda self: yazilan.append(self.karakter))
    d = S.NumpadDinleyici(gonder=gonderilen.append, sure=0.05, tus="numpad_arti")
    d.olay(_Ev("down"))
    d.olay(_Ev("down"))                                 # tuş tekrarı: yok sayılır
    time.sleep(0.15)
    d.olay(_Ev("up"))
    time.sleep(0.05)
    assert gonderilen == ["seçili metin"] and yazilan == []


def test_baska_tuslar_etkilenmez():
    d = S.NumpadDinleyici(gonder=lambda m: None, tus="numpad_arti")
    assert d.olay(_Ev("down", kod=30)) is True


def test_kilit_ayni_anda_tek_dinleyici(tmp_path, monkeypatch):
    import psutil
    kilit = str(tmp_path / "numpad.kilit")
    open(kilit, "w").write(str(os.getppid()))          # canlı başka bir işlem tutuyor
    gercek = psutil.Process
    monkeypatch.setattr(psutil, "Process", lambda pid: types.SimpleNamespace(
        cmdline=lambda: ["pythonw.exe", "C:/fenix/nobet_main.py"]))
    assert S._kilit_al(kilit) is False                  # o işlem bir FENIX işlemi (Nöbet)
    monkeypatch.setattr(psutil, "Process", lambda pid: types.SimpleNamespace(cmdline=lambda: ["chrome.exe"]))
    assert S._kilit_al(kilit) is True                   # 14.11: numara başka programa geçmişti; devralınır
    monkeypatch.setattr(psutil, "Process", gercek)
    open(kilit, "w").write("999999")                    # ölü işlem: devralınır
    assert S._kilit_al(kilit) is True
    S._kilit_birak(kilit)
    assert not os.path.exists(kilit)


def test_kisayol_tusu_degistirilebilir(monkeypatch):
    from modules import user_settings
    monkeypatch.setattr(user_settings, "get", lambda k, d=None: "f8" if k == "kisayol_tusu" else d)
    d = S.NumpadDinleyici(gonder=lambda m: None)
    assert d.tus == "f8" and d.kod == 66 and d.karakter is None
    assert d.olay(_Ev("down")) is True                  # artık Numpad + yutulmaz
    assert d.olay(_Ev("down", kod=66)) is False
    monkeypatch.setattr(user_settings, "get", lambda k, d=None: "olmayan_tus" if k == "kisayol_tusu" else d)
    assert S.tus_ayari() == "numpad_arti"


def test_yeniden_gonderilen_tus_gecer():
    d = S.NumpadDinleyici(gonder=lambda m: None, tus="f10")
    d._gecir = 2
    assert d.olay(_Ev("down", kod=68)) is True and d.olay(_Ev("up", kod=68)) is True
    assert d.olay(_Ev("down", kod=68)) is False
