# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Görev süre sınırı ve güncel bilgi algılama (13.11 testi).

- Bir arkadaşın 'selam' mesajına 15 dk sonra cevap geldi: görev artık belli bir sürede biter ve nedeni söylenir.
- "Bugün Bartın'da hava nasıl?" aramadan cevaplanmıştı (Kasım'da 25 °C)."""
import time

import pytest

from modules.llm_client import LLMClient, SureDoldu, GorevIptal


def _llm():
    return LLMClient("gemini-test", "groq-test", lazy_gemini=True)


def test_sure_dolunca_gorev_durur():
    llm = _llm()
    llm.son_tarih = time.time() - 1
    with pytest.raises(SureDoldu):
        llm._iptal_kontrol()


def test_sure_doldu_yedek_zincirlerinde_yakalanmaz():
    # 'except Exception' yedek-model zincirleri bunu yakalayıp başka modele geçmemeli
    assert issubclass(SureDoldu, GorevIptal) and not issubclass(SureDoldu, Exception)


def test_sure_yoksa_sinir_yok():
    llm = _llm()
    llm.son_tarih = None
    llm._iptal_kontrol()                                   # hata yok
    assert llm._kalan_sure(90) == 90


def test_ag_istegi_kalan_sureden_uzun_beklemez():
    llm = _llm()
    llm.son_tarih = time.time() + 20
    assert llm._kalan_sure(120) <= 20
    llm.son_tarih = time.time() + 1
    assert llm._kalan_sure(120) == 3.0                     # en az 3 sn (istek hiç gönderilemez olmasın)


def test_kota_dolunca_sebep_kaydedilir():
    llm = _llm()
    llm.groq_fallbacks = ["openai/gpt-oss-20b"]
    llm._groq_cooldown = {"openai/gpt-oss-120b": (time.time() + 3600, "14:00"),
                          "openai/gpt-oss-20b": (time.time() + 3600, "14:00")}
    with pytest.raises(Exception):
        llm._groq_with_fallback("normal", {"groq_model": "openai/gpt-oss-120b"}, "selam")
    assert any("günlük kotası" in s for s in llm.yavaslik)


@pytest.mark.parametrize("soru", ["Bugün Bartın'da hava nasıl?", "İstanbul'da yarın hava nasıl",
                                  "Bugün Türkiye'de öne çıkan bir haber söyler misin?", "Şu an 1 euro kaç TL?",
                                  "hava durumu ne"])
def test_guncel_sorular_aranir(soru):
    llm = _llm()
    llm._simdiki_istek = soru
    assert llm._guncel_mi()


@pytest.mark.parametrize("soru", ["Merhaba, bugün biraz yorgunum", "3 saat 45 dakika kaç dakika eder?",
                                  "haberin var mı bundan", "72 Fahrenheit kaç derece Celsius?",
                                  "1250 TL'lik bir ürüne %18 indirim yapılırsa kaç TL olur?",
                                  "Ayda 4500 TL biriktirirsem 1,5 yılda ne kadar birikir?"])
def test_siradan_sorular_aranmaz(soru):
    llm = _llm()
    llm._simdiki_istek = soru
    assert not llm._guncel_mi()


# --- İş türüne göre süre (Mustafa'nın fikri: her iş aynı sürede bitmez) ---
from modules import is_suresi as S


@pytest.mark.parametrize("metin,tur", [
    ("Merhaba, bugün biraz yorgunum", "sohbet"),
    ("selam", "sohbet"),
    ("1250 TL'lik ürüne %18 indirim yapılırsa kaç TL olur?", "hesap"),
    ("3 saat 45 dakika kaç dakika eder?", "hesap"),
    ("Bugün Bartın'da hava nasıl?", "guncel"),
    ("Şu an 1 euro kaç TL?", "guncel"),
    ("Masaüstüne alisveris.txt oluştur", "dosya"),
    ("Hesap makinesini aç", "bilgisayar"),
    ("10 dakika sonra bana çay demlendi diye hatırlat", "bilgisayar"),
    ("Python ile asal sayıları bulan bir kod yaz ve test et", "kod"),
    ("Bana Word belgesi olarak bir dilekçe yaz", "belge"),
    ("En iyi 5 laptopu araştırıp kaynaklı rapor hazırla", "arastirma"),
])
def test_is_turu(metin, tur):
    assert S.tur_bul(metin) == tur


def test_olcum_yoksa_varsayilan_tahmin():
    assert S.tahmin("sohbet") == S.TURLER["sohbet"][1]
    assert S.tahmin("kod") > S.tahmin("sohbet")


def test_ortalama_ogrenilir_ve_sinir_esner():
    once = S.sinir("kod")
    for sn in (200, 220, 240, 210):
        S.kaydet("kod", sn)
    assert S.tahmin("kod") == 215
    assert S.sinir("kod") > once                           # bu bilgisayarda kod işleri uzun sürüyor: sınır uzar
    assert S.sinir("kod") <= S.TURLER["kod"][2]            # ama tavanı geçmez


def test_kisa_isler_cabuk_kesilmez_ve_tavani_asmaz():
    for _ in range(5):
        S.kaydet("sohbet", 2)
    assert S.sinir("sohbet") == S.EN_KISA_SINIR            # 2 sn'lik ortalama yüzünden 8 sn'de kesilmez
    for _ in range(30):
        S.kaydet("sohbet", 500)
    assert S.sinir("sohbet") == S.TURLER["sohbet"][2]      # 15 dk 'selam' bir daha olmaz


def test_devil_daha_uzun_surebilir():
    for _ in range(5):
        S.kaydet("arastirma", 400)
    assert S.sinir("arastirma", "devil") > S.sinir("arastirma", "normal")


def test_bozuk_dosya_sorun_cikarmaz():
    import os
    os.makedirs("data", exist_ok=True)
    open(S.DOSYA, "w").write("bozuk{")
    assert S.tahmin("hesap") == S.TURLER["hesap"][1]
    S.kaydet("hesap", 5)                                   # yeniden yazılır
