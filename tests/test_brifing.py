# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Günlük brifing (v1.4)."""
import datetime

import pytest

from modules import brifing as B
from modules import user_settings


@pytest.mark.parametrize("saat,beklenen", [(7, "Günaydın"), (13, "İyi günler"), (19, "İyi akşamlar"),
                                           (23, "İyi geceler"), (3, "İyi geceler")])
def test_selamlama_saate_gore(saat, beklenen):
    assert B.selamlama(saat) == beklenen


def test_gunde_bir_kez():
    bugun = datetime.date(2026, 11, 14)
    assert not B.gerekli_mi(bugun)                     # hiç ayarlanmamış: önce sorulur
    B.kaydet(acik=True, icerik=["hava"], sehir="Bartın")
    assert B.gerekli_mi(bugun)
    B.gosterildi(bugun)
    assert not B.gerekli_mi(bugun)
    assert B.gerekli_mi(bugun + datetime.timedelta(days=1))


def test_kapaliysa_gosterilmez():
    B.kaydet(acik=False, icerik=["hava"])
    assert not B.gerekli_mi()


class _Store:
    def __init__(self, simdi):
        self.liste = [{"id": 1, "due": simdi.replace(hour=15, minute=0), "text": "ödev teslim"},
                      {"id": 2, "due": simdi - datetime.timedelta(days=1), "text": "faturayı öde"},
                      {"id": 3, "due": simdi + datetime.timedelta(days=2), "text": "doktor"}]

    def pending(self):
        return self.liste


def test_brifing_metni_aksam_acilisinda_gunaydin_demez():
    simdi = datetime.datetime(2026, 11, 14, 20, 30)
    B.kaydet(acik=True, icerik=["hava", "hatirlatma", "kur", "haber"], sehir="Bartın")
    m = B.olustur(_Store(simdi), simdi=simdi, kaynaklar={
        "hava": lambda s: "Bartın: parçalı bulutlu, 9–16 °C",
        "kur": lambda k: "1 USD = 34,50 TL", "haber": lambda: ["Başlık bir", "Başlık iki"]})
    assert m.startswith("İyi akşamlar! Bugün 14 Kasım Cumartesi.")
    assert "Günaydın" not in m
    assert "15:00 ödev teslim" in m and "Kaçırılan" in m and "faturayı öde" in m and "doktor" not in m
    assert "34,50 TL" in m and "• Başlık bir" in m


def test_sehir_yoksa_hava_istenmez():
    B.kaydet(acik=True, icerik=["hava"], sehir="")
    m = B.olustur(None, simdi=datetime.datetime(2026, 11, 14, 9), kaynaklar={"hava": lambda s: pytest.fail("istek")})
    assert "şehir seçilmemiş" in m


def test_hava_open_meteo_cozumlenir():
    def getir(url, **p):
        if "geocoding" in url:
            return {"results": [{"name": "Bartın", "latitude": 41.6, "longitude": 32.3}]}
        return {"daily": {"weathercode": [61], "temperature_2m_max": [15.6], "temperature_2m_min": [8.2],
                          "precipitation_probability_max": [70]}, "current_weather": {"temperature": 11.4}}
    h = B.hava("Bartın", getir=getir)
    assert h == "Bartın: hafif yağmurlu, 8–16 °C (şu an 11 °C), yağış ihtimali %70 — şemsiyeni al"


def test_hava_ag_hatasinda_none():
    def getir(url, **p):
        raise OSError("ağ yok")
    assert B.hava("Bartın", getir=getir) is None


def test_kur_ve_haber_cozumlenir():
    k = B.kurlar(["USD"], getir=lambda url, **p: {"rates": {"TRY": 34.567}})
    assert k == "1 USD = 34,57 TL"
    assert B.kurlar(["EUR"], getir=lambda url, **p: {"base": "EUR", "quote": "TRY", "rate": 37.1}) == "1 EUR = 37,10 TL"

    def v2_hata(url, **p):
        if "/v2/" in url:
            raise OSError("v2 yok")
        return {"rates": {"TRY": 30.0}}
    assert B.kurlar(["USD"], getir=v2_hata) == "1 USD = 30,00 TL"
    rss = ("<rss><channel><item><title>Deprem oldu - Haber Sitesi</title></item>"
           "<item><title>Maç sonucu - Spor</title></item></channel></rss>")
    assert B.haberler(2, getir=lambda url: rss) == ["Deprem oldu", "Maç sonucu"]


@pytest.mark.parametrize("metin,eslesir", [("brifing", True), ("Günün özeti", True), ("brifingi göster", True),
                                           ("brifing nedir, anlat bakalım", False), ("hava nasıl", False)])
def test_brifing_komutu(metin, eslesir):
    assert bool(B.KOMUT_RE.search(metin)) == eslesir


@pytest.mark.parametrize("metin,beklenen", [("Bartın, Bilecik", ["Bartın", "Bilecik"]),
                                            ("Bartın ve Bilecik", ["Bartın", "Bilecik"]),
                                            ("İstanbul", ["İstanbul"]), ("", [])])
def test_birden_fazla_sehir(metin, beklenen):
    """14.11: 'Bartın, Bilecik' tek bir yer gibi aranıp bulunamamıştı."""
    assert B.sehirleri_ayir(metin) == beklenen


def test_her_sehir_ayri_sorulur():
    B.kaydet(acik=True, icerik=["hava"], sehir="Bartın, Bilecik")
    sorulan = []
    m = B.olustur(None, simdi=datetime.datetime(2026, 11, 14, 9),
                  kaynaklar={"hava": lambda s: sorulan.append(s) or f"{s}: açık"})
    assert sorulan == ["Bartın", "Bilecik"] and "Bartın: açık" in m and "Bilecik: açık" in m


def test_serbest_brifing_istegi():
    B.kaydet(acik=True, icerik=[], ozel="")
    assert B.ozel_istek_metni() is None
    assert not B.gerekli_mi()                                   # hiçbir şey seçilmemiş
    B.kaydet(ozel="Galatasaray'ın son maçı, Bitcoin fiyatı")
    assert "Galatasaray'ın son maçı" in B.ozel_istek_metni()
    assert B.gerekli_mi()                                       # sadece serbest istek varsa da gösterilir
