# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Hafıza ve sohbet takibi: eski sohbet bulunur, gizli sohbet yazılmaz, uzun sohbette ilk soru kaybolmaz."""
from modules.memory import Memory


def yeni_hafiza():
    return Memory(db_path="data/test.db", semantic=False)


def test_eski_sohbet_kelimeyle_bulunur():
    m = yeni_hafiza()
    s1 = m.create_session(title="Kargocu projesi")
    m.add_message("user", "Kargocu projesinde rota optimizasyonunu konuşalım", session_id=s1)
    m.add_message("assistant", "Tamam, rota için en kısa yol algoritması kullanabiliriz.", session_id=s1)
    s2 = m.create_session(title="Yeni sohbet")
    m.current_session_id = s2
    sonuc = " ".join(m.keyword_search("Kargocu projesi hakkında ne konuşmuştuk?"))
    assert "Kargocu" in sonuc and "rota" in sonuc


def test_ekleri_farkli_kelime_de_bulunur():
    m = yeni_hafiza()
    s1 = m.create_session(title="Ödev")
    m.add_message("user", "Veritabanı ödevimi bitirdim", session_id=s1)
    m.current_session_id = m.create_session()
    assert "Veritabanı" in " ".join(m.keyword_search("veritabanı ödevi neydi"))


def test_gizli_sohbet_kaydedilmez():
    m = yeni_hafiza()
    m.current_session_id = None             # gizli sohbetin kayıtlı bir oturumu olmaz
    m.set_incognito(True)
    m.add_message("user", "GIZLIKELIME123 bunu kimse bilmesin")
    assert m.get_recent()                   # o an bellekte duruyor (sohbet devam edebilsin)
    m.set_incognito(False)
    assert m.count_matching("GIZLIKELIME123") == (0, 0)


def test_unut_komutu_kayitlari_siler():
    m = yeni_hafiza()
    s = m.create_session()
    m.add_message("user", "telefon numaram 0555 000 00 00", session_id=s)
    m.add_note("ev telefonu 0555 000 00 00")
    assert m.count_matching("0555 000 00 00") == (1, 1)
    m.forget_matching("0555 000 00 00")
    assert m.count_matching("0555 000 00 00") == (0, 0)


def _llm_ve_kayit(monkeypatch):
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    giden = []

    def sahte(payload, **k):
        giden.append(payload)
        return {"choices": [{"message": {"content": "tamam"}}]}
    monkeypatch.setattr(llm, "_groq_post", sahte)
    return llm, giden


def test_uzun_sohbette_ilk_soru_kaybolmaz(monkeypatch, ayar):
    """Geçen haftaki hata: bağlam her mesaja eklendiği için geçmiş kısaltılırken önceki sorular kesiliyordu."""
    llm, giden = _llm_ve_kayit(monkeypatch)
    mc = ayar["modes"]["normal"]
    uzun_baglam = "eski bilgi " * 400
    llm._groq_agent_chat("normal", mc, "Seni kim yarattı?", memory_context=uzun_baglam)
    for i in range(4):
        llm._groq_agent_chat("normal", mc, f"ara mesaj {i}", memory_context=uzun_baglam)
    llm._groq_agent_chat("normal", mc, "Maili var mı?", memory_context=uzun_baglam)
    mesajlar = giden[-1]["messages"]
    metin = " ".join(str(x.get("content")) for x in mesajlar)
    assert "Seni kim yarattı?" in metin, "İlk soru modele giden geçmişte yok"


def test_hafiza_baglami_sadece_son_mesaja_eklenir(monkeypatch, ayar):
    llm, giden = _llm_ve_kayit(monkeypatch)
    mc = ayar["modes"]["normal"]
    llm._groq_agent_chat("normal", mc, "birinci", memory_context="BAGLAM_A")
    llm._groq_agent_chat("normal", mc, "ikinci", memory_context="BAGLAM_B")
    kullanici = [x for x in giden[-1]["messages"] if x["role"] == "user"]
    assert "BAGLAM_A" not in kullanici[0]["content"]
    assert "BAGLAM_B" in kullanici[-1]["content"] and "ikinci" in kullanici[-1]["content"]
    # geçmişe yalnızca temiz metin yazılır
    assert [x["content"] for x in llm._groq_hist["normal"] if x["role"] == "user"] == ["birinci", "ikinci"]


def test_uzun_arac_zincirinde_gorev_unutulmaz(monkeypatch, ayar):
    """Kutu deneyinde bulunan hata: 7+ araç turundan sonra kullanıcının sorusu modele giden geçmişten düşüyordu."""
    from modules import functions as fx
    llm, giden = _llm_ve_kayit(monkeypatch)
    sayac = {"n": 0}

    def sahte(payload, **k):
        giden.append(payload)
        sayac["n"] += 1
        if sayac["n"] <= 10:
            return {"choices": [{"message": {"content": "", "tool_calls": [{"id": f"c{sayac['n']}", "type": "function",
                    "function": {"name": "list_folder", "arguments": "{\"folder\": \".\"}"}}]}}]}
        return {"choices": [{"message": {"content": "bitti"}}]}
    monkeypatch.setattr(llm, "_groq_post", sahte)
    monkeypatch.setitem(fx.WHITELISTED_FUNCTIONS, "list_folder", lambda **a: {"status": "ok"})
    llm.tur_siniri = 15
    llm._groq_agent_chat("normal", ayar["modes"]["normal"], "BODRUMDAKI_KUTU nerede?")
    for p in giden:
        m = p["messages"]
        assert any(x["role"] == "user" and "BODRUMDAKI_KUTU" in str(x.get("content")) for x in m)
        assert m[1]["role"] == "user"                       # sistemden sonra hep kullanıcı mesajı
        for i, x in enumerate(m):                            # her araç yanıtının çağrısı da gönderiliyor
            if x["role"] == "tool":
                assert any(y.get("tool_calls") and any(c["id"] == x["tool_call_id"] for c in y["tool_calls"])
                           for y in m[:i])


def test_bozuk_cevap_ekrana_basilmaz():
    from modules.llm_client import bozuk_cevap_temizle, BOZUK_CEVAP
    cop = "FENPDF — **FENIX** \n\n" + "\n\n".join(["…", "**…**", "...", "Ş", "(", "We …"] * 20) + "\n\nOops!"
    assert bozuk_cevap_temizle(cop) == BOZUK_CEVAP
    normal = "# FENIX Tanıtım\n\n| Yetenek | Açıklama |\n|---|---|\n" + "| Ekran | Ekranı okur ve açıklar. |\n" * 20
    assert bozuk_cevap_temizle(normal) == normal
    kod = "```python\n" + "for i in range(10):\n    print(i)\n" * 15 + "```"
    assert bozuk_cevap_temizle(kod) == kod


def test_tur_sonunda_model_isi_bitirmesi_icin_uyarilir(monkeypatch, ayar):
    """04.11: 6 turun hepsi search_web'e gitti, belge yazılmadı. Son iki turda 'işi bitir' uyarısı gider."""
    from modules import functions as fx
    llm, giden = _llm_ve_kayit(monkeypatch)

    def sahte(payload, **k):
        giden.append(payload)
        son = payload["messages"][-1]
        if "tools" not in payload:
            return {"choices": [{"message": {"content": "Belgeyi yazdım; rakip araştırması yarım kaldı."}}]}
        adlar = {t["function"]["name"] for t in payload["tools"]}
        if "search_web" not in adlar:                   # son turlarda arama aracı verilmez
            assert son["role"] == "system" and "işi ŞİMDİ bitir" in son["content"]
            return {"choices": [{"message": {"content": "", "tool_calls": [{"id": "w", "type": "function",
                    "function": {"name": "write_file", "arguments": "{\"path\": \"x.docx\", \"content\": \"# x\"}"}}]}}]}
        return {"choices": [{"message": {"content": "", "tool_calls": [{"id": f"s{len(giden)}", "type": "function",
                "function": {"name": "search_web", "arguments": "{\"query\": \"copilot\"}"}}]}}]}
    monkeypatch.setattr(llm, "_groq_post", sahte)
    yazilan = []
    monkeypatch.setitem(fx.WHITELISTED_FUNCTIONS, "search_web", lambda **a: {"status": "ok"})
    monkeypatch.setitem(fx.WHITELISTED_FUNCTIONS, "write_file", lambda **a: yazilan.append(a) or {"status": "ok"})
    cevap = llm._groq_agent_chat("normal", dict(ayar["modes"]["normal"], allow_actions=True),
                                 "belge yaz, rakipleri araştır")
    assert yazilan, "son turlarda dosya yazılmadı"
    assert "Belgeyi yazdım" in cevap and "Adım sınırına ulaşıldı" in cevap      # 'burada durdum' değil, özet
    uyarili = [p for p in giden if "işi ŞİMDİ bitir" in str(p["messages"][-1].get("content"))]
    assert len(uyarili) == 2 and "UYARI" not in str(giden[0]["messages"][-1])


def test_kendini_tanitan_belge_istegi_derin_arastirmaya_gitmez():
    from modules.agent import wants_deep_research
    istek = ('Masaüstüne "FENIX_Kapsamli_Tanitim.docx" adlı bir Word belgesi oluştur. Kendin hakkında yaz. '
             "Rakipler hakkındaki bilgileri araştır, diğer asistanlarla karşılaştır.")
    assert not wants_deep_research(istek)
    assert wants_deep_research("Elektrikli araba pazarını araştır ve karşılaştır")
    assert wants_deep_research("Copilot ile ChatGPT'yi karşılaştır, rapor hazırla")


def test_ekran_cevabi_ve_mod_degisimi_sohbeti_koparmaz(monkeypatch, ayar):
    """04.11 ekran görüntüsü: 'ekranıma bak' cevabı Gemini'den geldi, Groq görmedi; sonraki 'hayır, Word'ü sen oluştur'
    mesajında FENIX 'hangi içerik?' diye sordu. Mod değişince de konuşma kayboluyordu."""
    llm, giden = _llm_ve_kayit(monkeypatch)
    m = ayar["modes"]
    llm._groq_agent_chat("normal", m["normal"], "Kendini tanıtan bir belge hazırla")
    llm.ortak_kaydet("Kendini tanıtan bir belge hazırla", "tamam", kaynak=llm._son_kaynak)
    llm.ortak_kaydet("ekranıma bak", "UZUN_TANITIM_METNI ...", kaynak=("gemini", "normal", "gemini-x", 0))

    llm._groq_agent_chat("normal", m["normal"], "hayır Word belgesini sen oluştur")
    metin = " ".join(str(x.get("content")) for x in giden[-1]["messages"])
    assert "UZUN_TANITIM_METNI" in metin and "ekranıma bak" in metin
    assert metin.count("Kendini tanıtan bir belge hazırla") == 1          # aynı yolun kendi konuşması tekrar eklenmez
    llm.ortak_kaydet("hayır Word belgesini sen oluştur", "tamam", kaynak=llm._son_kaynak)

    llm._groq_agent_chat("devil", m["devil"], "şimdi bunu daha kapsamlı yap")    # mod değişti
    metin = " ".join(str(x.get("content")) for x in giden[-1]["messages"])
    for parca in ("Kendini tanıtan bir belge hazırla", "UZUN_TANITIM_METNI", "hayır Word belgesini sen oluştur"):
        assert parca in metin, parca
    u = [x for x in giden[-1]["messages"] if x["role"] == "user"]
    assert "şimdi bunu daha kapsamlı yap" in u[-1]["content"]


def test_ajan_her_yoldan_gelen_cevabi_ortak_kayda_yazar(monkeypatch, ayar):
    from modules.agent import Agent
    from modules.memory import Memory
    llm, giden = _llm_ve_kayit(monkeypatch)
    ag = Agent(llm, Memory(db_path="data/t2.db", semantic=False), notify=lambda *a: None)
    monkeypatch.setattr(ag, "_handle_ic", lambda *a, **k: {"text": "DERIN_RAPOR_OZETI"})
    ag.handle("elektrikli arabaları araştır", "devil", ayar["modes"]["devil"])
    assert llm._ortak[-1]["assistant"] == "DERIN_RAPOR_OZETI" and llm._ortak[-1]["kaynak"] is None
    llm._groq_agent_chat("normal", ayar["modes"]["normal"], "bunu Word yap")
    assert "DERIN_RAPOR_OZETI" in " ".join(str(x.get("content")) for x in giden[-1]["messages"])
