# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Mod önerisi: iş seçili moda göre büyükse FENIX uygun modu önerir, 'evet' denirse o moda geçilir."""
from modules import mod_onerisi as mo


def test_guvenli_modda_degisiklik_isteyen_is_normal_onerir():
    o = mo.oner("masaüstüme not.txt oluştur", "safe", "Güvenli modda dosya yazamıyorum.")
    assert o["mod"] == "normal" and "sadece okur" in o["sebep"]
    calls = [("write_file", {}, {"status": "error", "message": "Bu işlem bu modda yapılamaz."})]
    assert mo.oner("şunu kaydet", "safe", "Olmadı.", calls)["mod"] == "normal"


def test_adim_sinirina_takilan_is_devil_onerir():
    o = mo.oner("belge yaz", "normal", "Adım sınırına ulaştım (6 adım)...\n\n(Adım sınırına ulaşıldı.)")
    assert o["mod"] == "devil" and "adım" in o["sebep"]


def test_arastirma_istegi_devil_onerir_ama_kendi_belgesi_degil():
    assert mo.oner("Elektrikli araba pazarını araştır ve karşılaştır", "normal", "Kısa cevap.")["mod"] == "devil"
    kisa = 'Masaüstüne "FENIX.docx" adlı bir Word belgesi oluştur, kendini anlat ve rakiplerle karşılaştır.'
    assert mo.oner(kisa, "normal", "Belge oluşturuldu.") is None


def test_uzun_cok_parcali_is_baslamadan_sorulur():
    istek = "Şunu yap:\n" + "\n".join(f"{i}. bölüm: ayrıntılı yaz" for i in range(1, 9))
    assert mo.on_oneri(istek, "normal")["mod"] == "devil"
    assert mo.on_oneri(istek, "devil") is None and mo.on_oneri("sesi aç", "normal") is None
    assert "Başlamadan sorayım" in mo.on_soru_metni(mo.on_oneri(istek, "safe"), "safe")


def test_kucuk_is_ve_devil_modda_oneri_yok():
    assert mo.oner("sesi biraz aç", "normal", "Sesi %60 yaptım.") is None
    assert mo.oner("Elektrikli araba pazarını araştır", "devil", "Rapor hazır.") is None
    assert mo.oner("Elektrikli araba pazarını araştır", "ogrenme", "x") is None


def test_onay_ve_red_kelimeleri():
    for e in ("evet", "Evet!", "olur", "dene", "evet geç", "tamam devil moda geç", "geç"):
        assert mo.onay_mi(e), e
    for h in ("evet ama önce şu dosyayı da sil ve sonra bana bir rapor hazırla lütfen", "hayır", "neden?"):
        assert not mo.onay_mi(h), h
    assert mo.red_mi("hayır gerek yok") and mo.red_mi("kalsın")


def test_ajan_oneriyi_ekler_evet_deyince_gecis_verir_hayir_deyince_susar(monkeypatch, ayar):
    from modules.agent import Agent
    from modules.memory import Memory
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    ag = Agent(llm, Memory(db_path="data/t3.db", semantic=False), notify=lambda *a: None)
    cevaplar = iter(["Adım sınırına ulaştım.\n\n(Adım sınırına ulaşıldı.)", "tamam"] * 3)
    monkeypatch.setattr(ag, "_handle_ic", lambda *a, **k: next(cevaplar))
    istek = "Kendini tanıtan uzun bir belge yaz"
    r = ag.handle(istek, "normal", ayar["modes"]["normal"])
    assert "Devil moduna geçip tekrar deneyeyim mi?" in r and "adım" in r
    g = ag.mod_gecisi("evet")
    assert g == {"mod": "devil", "sebep": g["sebep"], "metin": istek}
    assert ag.mod_gecisi("evet") is None                       # öneri bir kez kullanılır

    ag.handle(istek, "normal", ayar["modes"]["normal"])         # yine öneri
    ag.handle("hayır kalsın", "normal", ayar["modes"]["normal"])
    r = ag.handle(istek, "normal", ayar["modes"]["normal"])     # reddedildi: tekrar önerilmez
    assert "deneyeyim mi" not in r


def test_buyuk_iste_once_sorar_evet_gecis_hayir_bu_modda_yapar(monkeypatch, ayar):
    from modules.agent import Agent
    from modules.memory import Memory
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    ag = Agent(llm, Memory(db_path="data/t4.db", semantic=False), notify=lambda *a: None)
    yapilan = []
    monkeypatch.setattr(ag, "_handle_ic", lambda t, *a, **k: yapilan.append(t) or "Belge oluşturuldu.")
    istek = "Belge yaz:\n" + "\n".join(f"{i}. bölüm: ayrıntılı anlat" for i in range(1, 12))
    r = ag.handle(istek, "normal", ayar["modes"]["normal"])
    assert "Başlamadan sorayım" in r and not yapilan                 # iş başlamadı, önce soruldu
    assert ag.mod_gecisi("evet")["metin"] == istek                    # evet -> uygulama Devil'a geçer

    ag.handle(istek, "normal", ayar["modes"]["normal"])               # tekrar sorar
    r = ag.handle("hayır", "normal", ayar["modes"]["normal"])         # hayır -> asıl istek Normal'de yapılır
    assert yapilan == [istek] and r.startswith("Belge oluşturuldu.")
    ag.handle(istek, "normal", ayar["modes"]["normal"])               # reddedildi: bir daha sormaz, yapar
    assert yapilan == [istek, istek]
