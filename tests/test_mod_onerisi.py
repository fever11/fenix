# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
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


def test_guvenli_modda_dosya_istegi_basta_sorulur_sohbet_istegi_sorulmaz():
    """07.11 testi: Güvenli modda 'deneme.txt oluştur' 200 sn takıldı; artık model çağrılmadan Normal önerilir."""
    assert mo.on_oneri('Masaüstüme deneme.txt diye bir dosya oluştur, içine "merhaba" yaz.', "safe")["mod"] == "normal"
    assert mo.on_oneri("sesi biraz aç", "safe")["mod"] == "normal"
    for sohbet in ("bana kısa bir şiir yaz", "Python ile Java farkını anlat", "saat kaç?"):
        assert mo.on_oneri(sohbet, "safe") is None, sohbet
    assert mo.on_oneri("Masaüstüme deneme.txt oluştur", "normal") is None


def test_sadece_karsilastir_kelimesi_devil_onermez():
    """07.11 testi: 'Aynı karşılaştırmayı C# için yap' isteğine gereksiz Devil önerisi çıktı."""
    assert mo.oner("Hayır, aslında Java değil C# demek istemiştim. Aynı karşılaştırmayı C# için yap.", "normal",
                   "Python dinamik tipli...") is None
    assert mo.oner("Elektrikli araba pazarını araştır", "normal", "Kısa cevap.")["mod"] == "devil"
    assert mo.oner("Bu konuda kaynaklı bir rapor hazırla", "normal", "Kısa cevap.")["mod"] == "devil"


def test_benim_hakkimda_ne_ogrendin_ders_listesi_dokmez():
    """07.11 testi (özel sürüm): 'benim hakkımda neler öğrendin?' öğrenme modülünün ders listesini döküyordu."""
    import pytest
    ogr = pytest.importorskip("modules.ogrenme")
    t = "Tamam, tekrar Türkçeye dönelim. Bu sohbette benim hakkımda neler öğrendin?"
    assert not (ogr._LAB_LIST.search(t) and not ogr._KISI_SORUSU.search(t))
    assert ogr._LAB_LIST.search("neler öğrendin?") and not ogr._KISI_SORUSU.search("neler öğrendin?")


def test_guvenli_modda_hayir_denince_islem_denenmez(monkeypatch, ayar):
    """07.11 üçüncü test: Güvenli modda 'sil' → 'hayır' denince FENIX yine silme onayı sordu."""
    from modules.agent import Agent
    from modules.memory import Memory
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    ag = Agent(llm, Memory(db_path="data/t5.db", semantic=False), notify=lambda *a: None)
    yapilan = []
    monkeypatch.setattr(ag, "_handle_ic", lambda t, *a, **k: yapilan.append(t) or "x")
    r = ag.handle("Masaüstündeki notlar.txt dosyasını sil.", "safe", ayar["modes"]["safe"])
    assert "Başlamadan sorayım" in r
    r = ag.handle("hayır", "safe", ayar["modes"]["safe"])
    assert "yapmadım" in r and not yapilan


def test_mod_gecisinden_sonra_tekrar_sormaz_ve_bilgiyi_sohbetten_alir(monkeypatch, ayar):
    """07.11 dördüncü test: 'evet' ile Normal'e geçilince FENIX 'Normal modda mı yapayım?' diye bir daha sordu,
    sonra sohbette zaten olan sınav tarihini istedi."""
    from modules.agent import Agent
    from modules.memory import Memory
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    giden = []
    monkeypatch.setattr(llm, "_groq_post", lambda p, **k: giden.append(p) or
                        {"choices": [{"message": {"content": "tamam"}}]})
    ag = Agent(llm, Memory(db_path="data/t6.db", semantic=False), notify=lambda *a: None)
    m = ayar["modes"]
    ag.handle("İki gün sonra sınava gireceğim, hangi gün?", "normal", m["normal"])
    istek = "Masaüstüne sinav_notu.txt oluştur, içine sınav tarihimi yaz."
    r = ag.handle(istek, "safe", m["safe"])
    assert "Başlamadan sorayım" in r
    assert all("Başlamadan sorayım" not in e["assistant"] for e in llm._ortak)
    g = ag.mod_gecisi("evet")
    llm.reset_mode_session(ortak_koru=True)
    giden.clear()
    ag.handle(g["metin"], "normal", m["normal"])
    son = [x for x in giden[-1]["messages"] if x["role"] == "user"][-1]["content"]
    assert "ONAYLADI" in son and "tekrar sorma" in son
    metin = " ".join(str(x.get("content")) for x in giden[-1]["messages"])
    assert "İki gün sonra sınava" in metin and "Başlamadan sorayım" not in metin


def test_normal_modda_rapor_istegi_basta_devil_sorulur():
    """07.11 dördüncü test: 'kaynaklı rapor hazırla' Normal'de 17 arama, 4 dk, boş sonuç."""
    o = mo.on_oneri("Türkiye'deki üniversite öğrencilerinin yapay zeka kullanımı hakkında kaynaklı bir rapor hazırla.",
                    "normal")
    assert o and o["mod"] == "devil"
    assert mo.on_oneri("Python ile Java farkını anlat", "normal") is None
    assert mo.on_oneri("kaynaklı bir rapor hazırla", "devil") is None


def test_yapmadan_yaptim_demesi_uyarilir(monkeypatch, ayar):
    """07.11 dördüncü test: 'özetle, sonra sinav_notu.txt'yi sil' → '[İşlem tamamlandı]' dendi, dosya silinmemişti."""
    from modules.agent import Agent
    from modules.memory import Memory
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    ag = Agent(llm, Memory(db_path="data/t7.db", semantic=False), notify=lambda *a: None)
    monkeypatch.setattr(ag, "_handle_ic", lambda *a, **k: "[İşlem tamamlandı]")
    r = ag.handle("Bu sohbeti özetle, sonra sinav_notu.txt dosyasını sil.", "normal", ayar["modes"]["normal"])
    assert "hiçbir değişiklik yapılmadı" in r

    def yapti(*a, **k):
        llm.last_calls = [("delete_file", {"path": "x"}, {"status": "ok"})]
        return "Dosya silindi."
    monkeypatch.setattr(ag, "_handle_ic", yapti)
    assert "Dikkat" not in ag.handle("sinav_notu.txt dosyasını sil", "normal", ayar["modes"]["normal"])
    monkeypatch.setattr(ag, "_handle_ic", lambda *a, **k: "Python 1991'de oluşturuldu.")
    assert "Dikkat" not in ag.handle("Python ne zaman çıktı?", "normal", ayar["modes"]["normal"])


def test_yerel_komutla_yapilan_isleme_yanlis_uyari_yok(monkeypatch, ayar):
    from modules.agent import Agent
    from modules.memory import Memory
    from modules.llm_client import LLMClient
    from modules import functions as fx
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    ag = Agent(llm, Memory(db_path="data/t8.db", semantic=False), notify=lambda *a: None)

    def yerel(*a, **k):
        fx.islem_say("Uygulama açılıyor: Hesap Makinesi")     # testte _notify susturulu; sayaç doğrudan
        return "Hesap Makinesi açıldı."
    monkeypatch.setattr(ag, "_handle_ic", yerel)
    assert "Dikkat" not in ag.handle("Hesap Makinesi'ni aç.", "normal", ayar["modes"]["normal"])

    def sadece_arama(*a, **k):
        fx.islem_say("Aranıyor: x")
        return "Dosya silindi."
    monkeypatch.setattr(ag, "_handle_ic", sadece_arama)
    assert "Dikkat" in ag.handle("x.txt dosyasını sil", "normal", ayar["modes"]["normal"])
