# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Ek yedek sağlayıcılar (v1.4): Groq dolunca yavaş NVIDIA'dan önce Mistral / SambaNova / OpenRouter."""
import pytest

from modules import yedekler
from modules.llm_client import LLMClient


@pytest.fixture(autouse=True)
def temiz():
    yedekler.configure({})
    yedekler._DINLEN.clear()
    yield
    yedekler.configure({})
    yedekler._DINLEN.clear()


def test_anahtar_yoksa_yedek_yok():
    yedekler.configure({"api_keys": {"mistral": "", "sambanova": "BURAYA_YAZ"}})
    assert yedekler.sira() == []


def test_anahtari_olanlar_sirayla():
    yedekler.configure({"api_keys": {"openrouter": "o", "mistral": "m"}})
    assert yedekler.sira() == ["openrouter", "mistral"]       # kartsız olanlar önce
    yedekler.configure({"api_keys": {"openrouter": "o", "mistral": "m"}, "yedekler": {"sira": ["openrouter", "mistral"]}})
    assert yedekler.sira() == ["openrouter", "mistral"]


def test_dinlenen_yedek_atlanir():
    yedekler.configure({"api_keys": {"mistral": "m", "sambanova": "s"}})
    yedekler.dinlendir("mistral")
    assert yedekler.sira() == ["sambanova"]


def test_saglayici_sirasi_nvidia_en_sonda():
    yedekler.configure({"api_keys": {"mistral": "m"}})
    llm = LLMClient("g", "groq-anahtar", lazy_gemini=True)
    llm._nvidia_models = lambda: ["nv"]
    assert llm._provider_order({"provider": "groq"}) == ["groq", "yedek:mistral", "nvidia"]


def test_mistral_uyarlamasi():
    yedekler.configure({"api_keys": {"mistral": "m"}})
    payload = {"model": "x", "tool_choice": {"type": "function", "function": {"name": "search_web"}},
               "messages": [{"role": "system", "content": "ana"},
                            {"role": "user", "content": "soru"},
                            {"role": "assistant", "content": "", "tool_calls": [
                                {"id": "call_abc123xyz_uzun", "type": "function",
                                 "function": {"name": "search_web", "arguments": "{}"}}]},
                            {"role": "tool", "tool_call_id": "call_abc123xyz_uzun", "content": "sonuç"},
                            {"role": "system", "content": "UYARI: son tur"}]}
    out = yedekler.uyarla("mistral", payload)
    roller = [m["role"] for m in out["messages"]]
    assert roller == ["system", "user", "assistant", "tool"]          # ara sistem notu başa taşındı
    assert "UYARI: son tur" in out["messages"][0]["content"]
    kimlik = out["messages"][2]["tool_calls"][0]["id"]
    assert len(kimlik) == 9 and kimlik.isalnum() and out["messages"][3]["tool_call_id"] == kimlik
    assert out["tool_choice"] == "any"
    assert payload["messages"][-1]["role"] == "system"                 # özgün istek değişmedi


def test_diger_saglayicilar_uyarlanmaz():
    yedekler.configure({"api_keys": {"sambanova": "s"}})
    p = {"messages": [{"role": "system", "content": "a"}, {"role": "system", "content": "b"}]}
    assert yedekler.uyarla("sambanova", p) is p


def test_groq_dolunca_mistral_kullanilir(monkeypatch):
    yedekler.configure({"api_keys": {"mistral": "m"}})
    llm = LLMClient("g", "groq-anahtar", lazy_gemini=True)
    llm._nvidia_models = lambda: []
    giden = []

    def sahte_groq(*a, **k):
        raise RuntimeError("groq günlük sınır")
    monkeypatch.setattr(llm, "_groq_with_fallback", sahte_groq)

    def sahte_post(payload, endpoint="groq", **k):
        giden.append(endpoint)
        return {"choices": [{"message": {"role": "assistant", "content": "Mistral cevabı"}}]}
    monkeypatch.setattr(llm, "_groq_post", sahte_post)
    llm._simdiki_istek = "selam"
    out = llm._fast_chain("normal", {"provider": "groq", "groq_model": "openai/gpt-oss-120b", "allow_actions": True},
                          "selam")
    assert "Mistral cevabı" in str(out)
    assert giden == ["yedek:mistral"]
    assert any("Mistral" in n for n in llm.yavaslik)


def test_yedek_hata_verirse_dinlenir_ve_nvidiaya_gecer(monkeypatch):
    yedekler.configure({"api_keys": {"mistral": "m"}})
    llm = LLMClient("g", "groq-anahtar", lazy_gemini=True)
    llm._nvidia_models = lambda: ["nv"]
    monkeypatch.setattr(llm, "_groq_with_fallback", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dolu")))
    monkeypatch.setattr(llm, "_nvidia_with_fallback", lambda *a, **k: "NVIDIA cevabı")

    def sahte_post(payload, endpoint="groq", **k):
        raise RuntimeError("429 rate limit")
    monkeypatch.setattr(llm, "_groq_post", sahte_post)
    llm._simdiki_istek = "selam"
    out = llm._fast_chain("normal", {"provider": "groq", "groq_model": "x", "allow_actions": True}, "selam")
    assert out == "NVIDIA cevabı"
    assert yedekler.sira() == []                                     # Mistral dinlendirildi


def test_dakika_sinirinda_en_fazla_bir_groq_modeline_gecilir_sonra_yedek(monkeypatch):
    """14.11: 120b, 20b ve qwen sırayla dakika sınırına takıldı; her biri aramayı baştan yaptı (138 sn+)."""
    import types
    yedekler.configure({"api_keys": {"sambanova": "s"}})
    llm = LLMClient("g", "groq-anahtar", lazy_gemini=True, groq_fallbacks=["openai/gpt-oss-20b", "qwen/qwen3.8-27b"])
    llm._nvidia_models = lambda: []
    denenen = []

    def sahte_agent(mode_key, mode_cfg, user_text, memory_context=""):
        denenen.append(mode_cfg["groq_model"])
        if mode_cfg.get("_endpoint", "groq") == "groq":
            hata = RuntimeError("429")
            hata.response = types.SimpleNamespace(status_code=429, text="Rate limit reached: tokens per minute (TPM)")
            raise hata
        return "SambaNova cevabı"
    monkeypatch.setattr(llm, "_groq_agent_chat", sahte_agent)
    out = llm._fast_chain("normal", {"provider": "groq", "groq_model": "openai/gpt-oss-120b", "allow_actions": True},
                          "hava")
    assert out == "SambaNova cevabı"
    assert denenen == ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "gpt-oss-120b"]


def test_degisiklik_yapildiysa_baska_saglayiciyla_bastan_baslanmaz(monkeypatch):
    """14.11: Groq dosyayı yazdı, sonra dakika sınırına takıldı; iş yedeğe verilip dosya ikinci kez yazılacaktı."""
    from modules import islem_defteri as DEF
    yedekler.configure({"api_keys": {"sambanova": "s"}})
    llm = LLMClient("g", "groq-anahtar", lazy_gemini=True)
    llm._nvidia_models = lambda: []
    yedege_gidildi = []

    def groq(*a, **k):
        DEF.kaydet("olusturma", "yedek_test.txt (Masaüstü)", "C:/x/yedek_test.txt", None)
        raise RuntimeError("429 dakika sınırı")
    monkeypatch.setattr(llm, "_groq_with_fallback", groq)
    monkeypatch.setattr(llm, "_yedek_with_fallback", lambda *a, **k: yedege_gidildi.append(1) or "tekrar")
    out = llm._fast_chain("normal", {"provider": "groq", "groq_model": "x", "allow_actions": True}, "dosya yaz")
    assert not yedege_gidildi
    assert out.startswith("Tamam, yaptım:") and "yedek_test.txt" in out and "ikinci kez" in out


def test_openrouter_varsayilan_modeli_ucretsiz_yonlendirici():
    assert yedekler.HAZIR["openrouter"]["modeller"][0] == "openrouter/free"


def test_cloudflare_hesap_numarasiyla_baglanir():
    yedekler.configure({"api_keys": {"cloudflare": "t", "cloudflare_hesap": "abc123"}})
    assert yedekler.sira() == ["cloudflare"]
    p = yedekler.bilgi("cloudflare")
    assert p["url"] == "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1/chat/completions"
    assert p["modeller"][0] == "@cf/openai/gpt-oss-120b"


def test_cloudflare_hesap_numarasi_yoksa_atlanir():
    yedekler.configure({"api_keys": {"cloudflare": "t"}})
    assert yedekler.sira() == []


def test_varsayilan_sira_kartsizlar_once():
    yedekler.configure({"api_keys": {"sambanova": "s", "cohere": "c", "openrouter": "o", "mistral": "m",
                                     "cloudflare": "t", "cloudflare_hesap": "h"}})
    assert yedekler.sira() == ["cloudflare", "openrouter", "cohere", "mistral", "sambanova"]


@pytest.mark.parametrize("icerik,bozuk", [("!" * 200, True), ("Hava 17 °C, parçalı bulutlu.", False),
                                         ("Sonuç: " + "a" * 60, True), ("Merhaba!!! Nasılsın?", False)])
def test_bozuk_cikti_algilanir(icerik, bozuk):
    """14.11: Cloudflare'daki gpt-oss cevap yerine '!!!!…' döndürdü."""
    llm = LLMClient("g", "k", lazy_gemini=True)
    veri = {"choices": [{"message": {"content": icerik}}]}
    if bozuk:
        with pytest.raises(RuntimeError):
            llm._bozuk_cikti_mi(veri, "yedek:cloudflare")
    else:
        llm._bozuk_cikti_mi(veri, "yedek:cloudflare")


def test_cloudflare_cevap_uzunlugu_belirtilir():
    """14.11: Workers AI uzunluk belirtilmeyince cevabı '…Öğle saat' diye yarıda kesti."""
    yedekler.configure({"api_keys": {"cloudflare": "t", "cloudflare_hesap": "h"}})
    out = yedekler.uyarla("cloudflare", {"messages": []})
    assert out["max_tokens"] >= 2048
    assert yedekler.uyarla("cloudflare", {"messages": [], "max_tokens": 100})["max_tokens"] == 100
