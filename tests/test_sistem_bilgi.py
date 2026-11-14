# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Sistem paneli verileri (v1.4)."""
from modules import sistem_bilgi as SB


def test_pil_raporu_cozulur():
    xml = "<Batteries><Battery><DesignCapacity>52500</DesignCapacity><FullChargeCapacity>44100</FullChargeCapacity>"
    assert SB.pil_xml_coz(xml) == {"yuzde": 84, "tasarim_mwh": 52500, "tam_sarj_mwh": 44100}
    assert SB.pil_xml_coz("") is None
    assert SB.pil_xml_coz("<DesignCapacity>0</DesignCapacity><FullChargeCapacity>1</FullChargeCapacity>") is None


def test_guvenlik_olaylari_saklanir_yeniden_eskiye():
    SB.olay_kaydet({"seviye": "dikkat", "baslik": "A", "kisa": "birinci"})
    SB.olay_kaydet({"seviye": "kritik", "baslik": "B", "kisa": "ikinci"})
    o = SB.son_olaylar(10)
    assert [x["kisa"] for x in o] == ["ikinci", "birinci"]


def test_olay_dosyasi_sinirli_kalir():
    for i in range(450):
        SB.olay_kaydet({"seviye": "dikkat", "baslik": "x", "kisa": str(i)})
    assert len(open(SB.OLAY_DOSYA, encoding="utf-8").readlines()) <= 400
    assert SB.son_olaylar(1)[0]["kisa"] == "449"


def test_anlik_ve_programlar_bicimi():
    a = SB.anlik()
    assert set(a) == {"cpu", "ram", "diskler", "ag", "gpu"}
    assert all({"ad", "yuzde", "bos_gb", "toplam_gb"} <= set(d) for d in a["diskler"])
    p = SB.en_cok_kullananlar(3)
    assert len(p) <= 3 and all({"ad", "ram_mb", "cpu", "pid", "adet"} <= set(x) for x in p)


def test_saglik_raporu_bolumleri():
    r = SB.saglik_raporu(buyuk_dosyalar=False)
    for bolum in ("ÖZET", "DİSKLER", "BELLEK (RAM)", "SON GÜVENLİK OLAYLARI"):
        assert bolum in r


def test_en_buyuk_dosyalar(tmp_path):
    (tmp_path / "kucuk.txt").write_bytes(b"a" * 10)
    (tmp_path / "buyuk.bin").write_bytes(b"a" * 5000)
    bd = SB.en_buyuk_dosyalar([str(tmp_path)], n=1)
    assert bd[0]["yol"].endswith("buyuk.bin")
