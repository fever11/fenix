# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Kendini tanı: FENIX kendisi hakkında tahmin etmez, gerçek durumu fenix_hakkinda aracından okur (04.11 testi)."""


def _kur(cfg):
    from modules import fenix_bilgi as fb
    fb.install(cfg)
    return fb, cfg


def test_modlar_dosya_adlari_degil_gercek_modlar(ayar):
    fb, cfg = _kur(ayar)
    m = fb.fenix_hakkinda("modlar")["message"]
    for k, mod in cfg["modes"].items():
        assert mod["label"] in m and mod["groq_model"] in m
    assert "llm_client" not in m and "pc_tools" not in m          # ilk testteki hata: dosyaları mod sanmıştı
    assert "en fazla 12 araç adımı" in m and "en fazla 6 araç adımı" in m


def test_modeller_ve_gizlilik_durust(ayar):
    fb, _ = _kur(ayar)
    m = fb.fenix_hakkinda()["message"]
    assert "Groq" in m and "Gemini" in m and "NVIDIA" in m
    assert "API'leri KULLANILMIYOR" in m                           # 'OpenAI/Claude ile çalışırım' demesin
    assert "İnternete çıkanlar" in m and "gönderilir" in m          # 'veriler dışarı çıkmaz' demesin
    assert "MODLAR" in m and "SINIRLAMALAR" in m and "EKLENTİLER" in m


def test_bolum_secimi_ve_hatali_bolum(ayar):
    fb, _ = _kur(ayar)
    assert fb.fenix_hakkinda("gizlilik")["message"].startswith("GÜVENLİK VE GİZLİLİK")
    assert fb.fenix_hakkinda("uydurma")["status"] == "error"


def test_kendi_hakkinda_isteklerde_arac_secilir_guvenli_modda_da(ayar):
    _kur(ayar)
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    cfg = ayar
    for istek in ('Masaüstüne "FENIX_Tanitim.docx" oluştur, kendini anlat', "hangi modların var?",
                  "neler yapabilirsin", "verilerim nereye gidiyor, gizlilik nasıl"):
        for mod in ("safe", "normal", "devil"):
            assert "fenix_hakkinda" in llm._select_tools(mod, cfg["modes"][mod], istek), (istek, mod)
    assert "fenix_hakkinda" not in llm._select_tools("normal", cfg["modes"]["normal"], "sesi biraz aç")


def test_sistem_talimati_once_araci_cagirmasini_soyler(ayar):
    from modules.llm_client import build_system_instruction
    t = build_system_instruction("normal", ayar["modes"]["normal"])
    assert "ÖNCE fenix_hakkinda" in t and "BAĞLANMAZSIN" in t


def test_kendisi_sorulunca_gercek_bilgi_baglama_eklenir(ayar):
    """04.11 üçüncü deneme: araç vardı ama model çağırmadı, modları yine uydurdu. Artık bilgi doğrudan eklenir."""
    _kur(ayar)
    from modules.agent import kendi_bilgisi
    b = kendi_bilgisi('Masaüstüne "FENIX_Tanitim.docx" oluştur, kendini anlat, modlarını yaz')
    assert "GERÇEK bilgiler" in b and "MODLAR" in b and "Devil" in b
    assert kendi_bilgisi("hangi modların var fenix?")
    for alakasiz in ("fenix klasörünü aç", "sesi aç", "kocdetailing projesinin son commiti ne"):
        assert kendi_bilgisi(alakasiz) == "", alakasiz


def test_uzun_istekte_bolum_kelimeleri_arac_yagdirmaz(ayar):
    """11 bölümlü belge isteği 33 aracı birden seçiyordu (her adımda Groq dakika sınırı)."""
    _kur(ayar)
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    istek = ('Masaüstüne "FENIX_Kapsamli.docx" adlı bir Word belgesi oluştur, kendini anlat. Rakipleri araştır.\n'
             + "\n".join(f"{i}. bölüm: hatırlatma, güvenlik taraması, ses ayarı, kısayol, ekran, süreç durdurma, "
                         "pencere, medya, hafıza ve unutma hakkında yaz." for i in range(1, 12)))
    sec = llm._select_tools("devil", ayar["modes"]["devil"], istek)
    assert {"write_file", "search_web", "fenix_hakkinda"} <= sec
    assert not sec & {"set_reminder", "stop_process", "set_voice", "save_shortcut", "media_control"}
    assert len(sec) <= 15
    assert "set_reminder" in llm._select_tools("normal", ayar["modes"]["normal"], "yarın 9'da hatırlat")
