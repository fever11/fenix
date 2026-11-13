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


# --- Hafif yol (13.11: ardı ardına basit sorular Groq'un dakikalık token sınırına takılıyordu) ---
from modules.llm_client import build_light_instruction, build_system_instruction


def test_hafif_talimat_kisa_ve_kurallari_tasir():
    hafif = build_light_instruction("normal")
    assert len(hafif) * 3 < len(build_system_instruction("normal", {"allow_actions": True}))
    assert "Mustafa Koç" in hafif and "iletişim" in hafif          # yaratıcı + iletişim bilgisi gizliliği
    assert "Türkçe" in hafif


@pytest.mark.parametrize("soru", ["Selam, nasılsın?", "850 TL'lik ayakkabıya %25 indirim yapılırsa kaç TL öderim?",
                                  "Bana uzay hakkında ilginç bir bilgi ver.", "Biraz daha esprili yap.",
                                  "bana bir şiir yaz", "Benim adım neydi?"])
def test_basit_sorular_hafif(soru):
    llm = _llm()
    llm._simdiki_istek = soru
    assert llm._hafif_mi("normal", soru, [])


@pytest.mark.parametrize("soru", ["Bugün dolar kaç TL?", "Not Defteri'ni aç.", "bunu unut", "ekranda ne var",
                                  "sesi %50 yap", "5 dakika sonra su iç diye hatırlat", "evet",
                                  "O dosyaya spor yap maddesini ekle.", "Sen hangi lisansla dağıtılıyorsun, fenix?",
                                  "Python ile bir kod yaz"])
def test_arac_gereken_sorular_tam_yol(soru):
    llm = _llm()
    llm._simdiki_istek = soru
    assert not llm._hafif_mi("normal", soru, [])


def test_teklife_cevap_tam_yol():
    llm = _llm()
    llm._simdiki_istek = "olur bakalım"
    h = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "Not Defteri'ni açayım mı?"},
         {"role": "user", "content": "olur bakalım"}]
    assert not llm._hafif_mi("normal", "olur bakalım", h)


def test_hafif_istekte_arac_gonderilmez(monkeypatch):
    llm = _llm()
    giden = []

    def sahte(payload, endpoint="groq", **k):
        giden.append(payload)
        return {"choices": [{"message": {"role": "assistant", "content": "Selam! İyiyim."}}]}
    monkeypatch.setattr(llm, "_groq_post", sahte)
    llm._simdiki_istek = "Selam, nasılsın?"
    cevap = llm._groq_agent_chat_ic("normal", {"groq_model": "openai/gpt-oss-120b", "allow_actions": True},
                                    "Selam, nasılsın?")
    assert "İyiyim" in str(cevap)
    assert "tools" not in giden[0] and len(giden[0]["messages"][0]["content"]) < 3000


def test_hafif_yol_yetmezse_tam_yola_gecer(monkeypatch):
    """Güvenlik ağı: kısa talimat soruyu karşılayamazsa model [TAM_YOL] der, tam talimat + araçlarla yeniden sorulur."""
    llm = _llm()
    giden = []
    cevaplar = iter([{"role": "assistant", "content": "[TAM_YOL]"},
                     {"role": "assistant", "content": "Tam cevap."}])

    def sahte(payload, endpoint="groq", **k):
        giden.append(payload)
        return {"choices": [{"message": next(cevaplar)}]}
    monkeypatch.setattr(llm, "_groq_post", sahte)
    notlar = []
    llm.not_yaz = notlar.append
    llm._simdiki_istek = "Bana ilginç bir şey söyle"
    cevap = llm._groq_agent_chat_ic("normal", {"groq_model": "openai/gpt-oss-120b", "allow_actions": True},
                                    "Bana ilginç bir şey söyle")
    assert cevap == "Tam cevap."
    assert "tools" not in giden[0] and "tools" in giden[1]
    assert len(giden[1]["messages"][0]["content"]) > 5000          # tam talimat
    assert not any("[TAM_YOL]" in str(m.get("content")) for m in giden[1]["messages"])   # geçmişe girmedi
    assert any("yetmedi" in n for n in notlar)


# --- 13.11 ikinci deneme: art arda sorular + "Bu akşam Ankara'da yağmur var mı?" 1 dk 30 sn'de kesildi ---
import requests


def _hata429(metin="Rate limit reached ... tokens per minute (TPM): Limit 8000"):
    r = requests.Response()
    r.status_code = 429
    r._content = metin.encode()
    return requests.HTTPError("429", response=r)


def test_dakikalik_sinirda_siradaki_groq_modeline_gecer(monkeypatch):
    llm = _llm()
    llm.groq_fallbacks = ["openai/gpt-oss-20b"]
    denenen = []

    def sahte(mode_key, mode_cfg, user_text, memory_context=""):
        denenen.append((mode_cfg["groq_model"], llm._dk_bekleme_siniri))
        if mode_cfg["groq_model"].endswith("120b"):
            raise _hata429()
        return "20b cevabı"
    monkeypatch.setattr(llm, "_groq_agent_chat", sahte)
    out = llm._groq_with_fallback("normal", {"groq_model": "openai/gpt-oss-120b"}, "soru")
    assert out == "20b cevabı"
    assert denenen[0] == ("openai/gpt-oss-120b", 5)          # sırada model varken uzun beklenmez
    assert any("dakikalık" in y for y in llm.yavaslik)
    # bir sonraki soruda dakika kotası dolu model sona alınır
    denenen.clear()
    llm._groq_with_fallback("normal", {"groq_model": "openai/gpt-oss-120b"}, "soru 2")
    assert denenen[0][0] == "openai/gpt-oss-20b"


def test_islem_yapildiysa_model_degistirip_bastan_almaz(monkeypatch):
    from modules import functions as fx
    llm = _llm()
    llm.groq_fallbacks = ["openai/gpt-oss-20b"]

    def sahte(mode_key, mode_cfg, user_text, memory_context=""):
        fx.ISLEM_SAYACI[0] += 1                               # ör. dosya yazıldı, sonra sınıra takıldı
        raise _hata429()
    monkeypatch.setattr(llm, "_groq_agent_chat", sahte)
    with pytest.raises(requests.HTTPError):
        llm._groq_with_fallback("normal", {"groq_model": "openai/gpt-oss-120b"}, "dosya oluştur")


@pytest.mark.parametrize("soru", ["Bu akşam Ankara'da yağmur var mı?", "yarın kar var mı", "hava durumu nasıl"])
def test_hava_sorulari_guncel(soru):
    llm = _llm()
    llm._simdiki_istek = soru
    assert llm._guncel_mi() and not llm._hafif_mi("normal", soru, [])
    assert S.tur_bul(soru) == "guncel"


def test_tam_yola_gecince_sure_uzar(monkeypatch):
    llm = _llm()
    cevaplar = iter([{"content": "[TAM_YOL]"}, {"content": "Tamam."}])
    monkeypatch.setattr(llm, "_groq_post", lambda payload, **k: {"choices": [{"message": next(cevaplar)}]})
    llm.son_tarih = time.time() + 10
    llm._simdiki_istek = "ilginç bir şey söyle"
    llm._groq_agent_chat_ic("normal", {"groq_model": "openai/gpt-oss-120b", "allow_actions": True},
                            "ilginç bir şey söyle")
    assert llm.son_tarih - time.time() > 100


def test_hafif_yetmeyince_is_turu_agirlasir_ve_yedekte_tekrar_denenmez(monkeypatch):
    """13.11: 'Bu akşam Ankara'da yağmur var mı?' hafif yoldan başladı, tam yola geçti, aramaya döndü; ama süre hâlâ
    'sohbet' (90 sn) sayıldı ve yedek modelde soru YİNE hafif yoldan denendi."""
    llm = _llm()
    turler = []
    llm.tur_degisti = turler.append
    cevaplar = iter([{"role": "assistant", "content": "[TAM_YOL]"},
                     {"role": "assistant", "content": "", "tool_calls": [{"id": "a", "type": "function",
                      "function": {"name": "search_web", "arguments": "{\"query\": \"x\"}"}}]},
                     {"role": "assistant", "content": "Yağmur yok."}])
    monkeypatch.setattr(llm, "_groq_post", lambda payload, **k: {"choices": [{"message": next(cevaplar)}]})
    from modules import functions as fx
    monkeypatch.setitem(fx.WHITELISTED_FUNCTIONS, "search_web", lambda **a: {"status": "ok", "results": []})
    soru = "Bu gece dışarı çıksam üşür müyüm sence"
    llm._simdiki_istek = soru
    assert llm._hafif_mi("normal", soru, [])
    llm._groq_agent_chat_ic("normal", {"groq_model": "openai/gpt-oss-120b", "allow_actions": True}, soru)
    assert turler[:2] == ["tam", "guncel"]                          # tam yola geçiş (süre uzar) + arama (tür)
    assert not llm._hafif_mi("normal", soru, [])                   # yedek modelde hafif yol tekrar denenmez


def test_ankara_yagmur_sorusu_aranir():
    llm = _llm()
    llm._simdiki_istek = "Bu akşam Ankara'da yağmur var mı?"
    assert llm._guncel_mi() and not llm._hafif_mi("normal", llm._simdiki_istek, [])


def test_ogrenme_siniri_varsayilanin_altina_indirmez():
    """13.11: hızlı aramalardan sonra 'güncel' ortalaması ~4 sn oldu, sınır 90 sn'ye indi; kotaya takılan arama kesildi."""
    for _ in range(10):
        S.kaydet("guncel", 4)
    assert S.sinir("guncel") >= S.TURLER["guncel"][1] * S.CARPAN


def test_kota_beklemesi_sureye_eklenir_ama_sinirli():
    llm = _llm()
    llm.son_tarih = 1000.0
    llm.eklenen_sure = 0.0
    llm._sure_ekle(40)
    llm._sure_ekle(40)
    llm._sure_ekle(80)
    assert llm.son_tarih == 1000.0 + llm._EK_SURE_EN_FAZLA
