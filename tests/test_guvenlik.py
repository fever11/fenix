# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Güvenlik kuralları: riskli komut onaysız çalışmaz, web komutu engellenir, Güvenli mod sisteme dokunmaz."""
import pytest

from modules import functions as fx

RISKLI = [
    "Remove-Item C:\\Users\\x\\belge.txt",
    "del C:\\Users\\x\\belge.txt",
    "rm C:\\Users\\x\\belge.txt",
    "rm -r C:\\Users\\x\\proje",
    "ri C:\\temp\\a.txt",
    "erase a.txt",
    "rd /s /q C:\\temp",
    "rmdir C:\\temp",
    "Format-Volume -DriveLetter D",
    "format d:",
    "shutdown /s /t 0",
    "Restart-Computer",
    "Stop-Process -Name chrome",
    "kill -Name chrome",
    "spps -Name chrome",
    "taskkill /im chrome.exe /f",
    "reg delete HKCU\\Software\\X /f",
    "Set-ExecutionPolicy Unrestricted",
    "Clear-RecycleBin -Force",
    "net user misafir /add",
    "Get-ChildItem C:\\x | Remove-Item",
    "Get-ChildItem C:\\x | rm",
    "Uninstall-Package x",
]
GUVENLI = [
    "Get-Date",
    "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5",
    "dir $env:USERPROFILE\\Desktop",
    "Get-ChildItem C:\\Users\\x\\Desktop -Filter *.pdf",
    "Get-Content C:\\Users\\x\\not.txt",
    "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version",
    "ipconfig /all",
]


@pytest.mark.parametrize("komut", RISKLI)
def test_riskli_komut_taninir(komut):
    assert fx._is_risky(komut), f"Riskli komut tanınmadı: {komut}"


@pytest.mark.parametrize("komut", GUVENLI)
def test_zararsiz_komut_riskli_sayilmaz(komut):
    assert not fx._is_risky(komut), f"Zararsız komut gereksiz yere riskli sayıldı: {komut}"


def test_riskli_komut_onaysiz_calismaz(monkeypatch):
    sorulan = []
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: sorulan.append(a) or False)
    r = fx.run_command("Remove-Item C:\\Users\\x\\proje -Recurse", "Proje klasörünü sil")
    assert sorulan, "Riskli komut için onay sorulmadı"
    assert r["status"] == "cancelled"          # _exec_ps çağrılsaydı test hata verirdi (conftest)


def test_riskli_komut_onaylaninca_calisir(monkeypatch):
    calisan = []
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: True)
    monkeypatch.setattr(fx, "_exec_ps", lambda c, *a, **k: calisan.append(c) or {"status": "ok", "message": ""})
    fx.run_command("Remove-Item C:\\temp\\a.txt", "Dosyayı sil")
    assert calisan == ["Remove-Item C:\\temp\\a.txt"]


@pytest.mark.parametrize("komut", ["Invoke-WebRequest https://ornek.com -OutFile a.exe",
                                   "iwr https://ornek.com", "curl https://ornek.com",
                                   "(New-Object Net.WebClient).DownloadString('https://ornek.com')"])
def test_web_komutu_engellenir(monkeypatch, komut):
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: pytest.fail("Web komutu onay kutusuna düşmemeli"))
    r = fx.run_command(komut, "indir")
    assert r["status"] == "error" and "read_webpage" in r["message"]


def test_uzun_dosya_yazma_komutu_write_file_araci_na_yonlendirilir():
    komut = "Set-Content -Path C:\\x\\index.html -Value @'\n<html>" + "a" * 1500 + "</html>\n'@"
    r = fx.run_command(komut, "site yaz")
    assert r["status"] == "error" and "write_file" in r["message"]


TEHLIKELI_ARACLAR = {"run_command", "write_file", "edit_file", "open_app_by_name", "open_url", "open_folder_by_name",
                     "set_system_volume", "stop_process", "remove_startup_program", "restore_startup_program",
                     "enable_protection"}


def test_salt_okuma_listesinde_sisteme_dokunan_arac_yok():
    sizan = TEHLIKELI_ARACLAR & fx.READONLY_FUNCTIONS
    assert not sizan, f"Güvenli modda kullanılabilen tehlikeli araç: {sizan}"


def test_salt_okuma_araclari_gercekten_var():
    yok = fx.READONLY_FUNCTIONS - set(fx.WHITELISTED_FUNCTIONS)
    assert not yok, f"Salt okuma listesinde olup tanımlı olmayan araç: {yok}"


def test_guvenli_modda_model_komut_calistirmaya_kalkarsa_reddedilir(monkeypatch, ayar):
    from modules.llm_client import LLMClient
    llm = LLMClient("", "gsk_TEST_ANAHTARI_GERCEK_DEGIL", lazy_gemini=True)
    cevaplar = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "run_command",
                          "arguments": '{"command": "Remove-Item C:\\\\x -Recurse", "description": "sil"}'}}]}}]},
        {"choices": [{"message": {"content": "Bu modda yapamam."}}]},
    ]
    monkeypatch.setattr(llm, "_groq_post", lambda payload, **k: cevaplar.pop(0))
    monkeypatch.setattr(fx, "run_command", lambda *a, **k: pytest.fail("Güvenli modda run_command çalıştı!"))
    monkeypatch.setitem(fx.WHITELISTED_FUNCTIONS, "run_command",
                        lambda *a, **k: pytest.fail("Güvenli modda run_command çalıştı!"))
    out = llm._groq_agent_chat("safe", ayar["modes"]["safe"], "masaüstündeki x klasörünü sil")
    sonuc = llm.last_calls[-1]
    assert sonuc[0] == "run_command" and sonuc[2]["status"] == "error"
    assert out == "Bu modda yapamam."


def test_codeql_duzeltmeleri_kalici():
    """GitHub CodeQL uyarıları (05.11): TLS en az 1.2, imza yorumu regex'siz gizlenir, emoji kalıbı açık yazılır."""
    import inspect
    from modules import security, web_analyzer, audit_rules
    from modules.report_export import _gizli_yorum
    for fn in (security._cert_info, web_analyzer._tls_info):
        assert "TLSv1_2" in inspect.getsource(fn)
    assert _gizli_yorum("<!-- Core: MK-Agentic-System -->") and not _gizli_yorum("<!-- a --> metin <!-- b -->")
    assert audit_rules._EMOJI_RE.sub("", "Merhaba 😀 ☀️ dünya") == "Merhaba   dünya"
