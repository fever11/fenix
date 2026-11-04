# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Yol hafızası: bir projede öğrenilen yol BAŞKA bir projede de ipucu olarak kullanılır; klasör yoksa ipucu yok."""
import os

from modules import yol_hafizasi as yh


def _depo(kok, ad):
    p = os.path.join(kok, ad)
    os.makedirs(os.path.join(p, ".git"))
    return p


def test_proje_klasorleri_taranir(tmp_path):
    a = _depo(str(tmp_path), "KocDetailing")
    b = _depo(os.path.join(str(tmp_path), "github projeler"), "fenix")
    os.makedirs(os.path.join(str(tmp_path), "node_modules", "x", ".git"))
    bulunan = yh.projeleri_tara([str(tmp_path)])
    assert bulunan == {"KocDetailing": a, "fenix": b}


def test_projeyi_metinden_bulur(tmp_path):
    a = _depo(str(tmp_path), "KocDetailing")
    liste = {"KocDetailing": a, "fenix": _depo(str(tmp_path), "fenix")}
    assert yh.projeyi_bul("koc detailing değil kocdetailing'deki commitler", liste)[0] == "KocDetailing"
    assert yh.projeyi_bul("FENIX projesinde ne değişti", liste)[0] == "fenix"
    assert yh.projeyi_bul("hava nasıl", liste) is None


def test_bir_projede_ogrenilen_yol_baska_projede_ipucu_olur(tmp_path):
    koc = _depo(str(tmp_path), "KocDetailing")
    fenix = _depo(str(tmp_path), "fenix")
    calls = [("find_files", {"name": "KocDetailing", "folder": "masaüstü"}, {"status": "ok"}),
             ("mcp_git_git_log", {"repo_path": koc, "max_count": 10}, {"status": "ok", "message": "..."})]
    y = yh.ogren("KocDetailing projesindeki son commitleri göster", calls)
    assert y and y["proje"] == "KocDetailing"
    assert [s["arac"] for s in y["adimlar"]] == ["mcp_git_git_log"]          # arama adımı şablona girmez
    assert y["adimlar"][0]["arg"]["repo_path"] == "{proje_yolu}"
    metin, araclar = yh.ipucu("fenix projesindeki son commitleri göster", {"KocDetailing": koc, "fenix": fenix})
    assert araclar == {"mcp_git_git_log"}
    assert fenix in metin and koc not in metin.split("→", 1)[-1].split("Benzer")[0]
    assert '"repo_path": "' in metin


def test_ilgisiz_istekte_ipucu_yok(tmp_path):
    koc = _depo(str(tmp_path), "KocDetailing")
    yh.ogren("KocDetailing projesindeki son commitleri göster",
             [("mcp_git_git_log", {"repo_path": koc}, {"status": "ok"})])
    metin, araclar = yh.ipucu("bugün hava nasıl olacak", {"KocDetailing": koc})
    assert metin == "" and araclar == set()


def test_basarisiz_is_ogrenilmez_ve_gizli_sohbet_kaydedilmez(tmp_path):
    koc = _depo(str(tmp_path), "KocDetailing")
    assert yh.ogren("KocDetailing commitleri", [("mcp_git_git_log", {"repo_path": koc}, {"status": "error"})]) is None
    assert yh.ogren("KocDetailing commitleri", [("mcp_git_git_log", {"repo_path": koc}, {"status": "ok"})],
                    incognito=True) is None
    assert yh.yollar() == []


def test_kapatilinca_ipucu_vermez(tmp_path):
    from modules import user_settings
    koc = _depo(str(tmp_path), "KocDetailing")
    yh.ogren("KocDetailing projesindeki commitler", [("mcp_git_git_log", {"repo_path": koc}, {"status": "ok"})])
    user_settings.set("yol_hafizasi", False)
    assert yh.ipucu("KocDetailing projesindeki commitler", {"KocDetailing": koc}) == ("", set())


def test_klasor_silinince_proje_listesinden_duser(tmp_path):
    import shutil
    koc = _depo(str(tmp_path), "KocDetailing")
    yh.proje_ekle("KocDetailing", koc)
    assert "KocDetailing" in yh.projeler()
    shutil.rmtree(koc)
    assert "KocDetailing" not in yh.projeler()


def test_ajan_ipucunu_modele_verir_ve_olcer(tmp_path, monkeypatch, ayar):
    from modules.agent import Agent
    from modules.memory import Memory
    koc = _depo(str(tmp_path), "KocDetailing")
    fenix = _depo(str(tmp_path), "fenix")
    yh.proje_ekle("KocDetailing", koc)
    yh.proje_ekle("fenix", fenix)
    yh.ogren("KocDetailing projesindeki son commitleri göster",
             [("mcp_git_git_log", {"repo_path": koc, "max_count": 10}, {"status": "ok"})])

    class SahteLLM:
        last_calls = []
        _extra_tools = set()

        def ask(self, mode_key, mode_cfg, message, memory_context=""):
            self.gorulen = (memory_context, set(self._extra_tools))
            self.last_calls = [("mcp_git_git_log", {"repo_path": fenix}, {"status": "ok"})]
            return "tamam"
    llm = SahteLLM()
    ag = Agent(llm, Memory(db_path="data/t.db", semantic=False))
    ag.handle("fenix projesindeki son commitleri göster", "normal", ayar["modes"]["normal"])
    baglam, araclar = llm.gorulen
    assert "Yol hafızası" in baglam and fenix in baglam and araclar == {"mcp_git_git_log"}
    olcum = open(yh.OLCUM_PATH, encoding="utf-8").read()
    assert '"ipucu": true' in olcum and '"arac_sayisi": 1' in olcum


def test_bosluklu_yazilan_proje_adi_da_taninir(tmp_path):
    koc = _depo(str(tmp_path), "KocDetailing")
    fenix = _depo(str(tmp_path), "fenix")
    liste = {"KocDetailing": koc, "fenix": fenix}
    assert yh.projeyi_bul("koc detailing hakkında commitlerimi görebiliyor musun", liste)[0] == "KocDetailing"
    y = yh.ogren("koc detailing hakkında commitlerimi görebiliyor musun",
                 [("mcp_git_git_log", {"repo_path": koc}, {"status": "ok"})])
    assert y["proje"] == "KocDetailing" and "{proje}" in y["kalip"]
    metin, araclar = yh.ipucu("fenix hakkında commitlerimi görebiliyor musun", liste)
    assert araclar == {"mcp_git_git_log"} and fenix in metin


def test_ogrenilen_klasorun_yanindakiler_de_bilinir(tmp_path):
    raf = os.path.join(str(tmp_path), "bodrum", "raf_3")
    kutu = _depo(raf, "mavi_kutu")
    _depo(raf, "lamba")
    os.makedirs(os.path.join(raf, "eski_koli"))
    yh.ogren("bodrumdaki mavi_kutu projesinin son commit mesajı ne",
             [("list_folder", {"folder": raf}, {"status": "ok"}),
              ("mcp_git_git_log", {"repo_path": kutu}, {"status": "ok"})])
    metin, _ = yh.ipucu("mavi_kutu'nun yanındaki lamba projesinin son commit mesajı ne")
    assert kutu in metin and "lamba" in metin and "eski_koli" in metin


def test_metinde_ust_klasor_de_gecse_asil_proje_ogrenilir(tmp_path):
    """Kutu deneyinde bulunan hata: istekte bodrum klasörünün yolu da geçince proje olarak 'bodrum' öğreniliyordu."""
    bodrum = os.path.join(str(tmp_path), "bodrum_1")
    raf = os.path.join(bodrum, "raf_2", "koli_1")
    kutu = _depo(raf, "mavi_kutu")
    y = yh.ogren(f"Bodrum klasörü: {bodrum}. Bu bodrumdaki mavi_kutu projesinin son commit mesajı ne?",
                 [("list_folder", {"folder": bodrum}, {"status": "ok"}),
                  ("list_folder", {"folder": raf}, {"status": "ok"}),
                  ("mcp_git_git_log", {"repo_path": kutu}, {"status": "ok"})])
    assert y["proje"] == "mavi_kutu"
    assert yh.projeler().get("mavi_kutu") == kutu and "bodrum_1" not in yh.projeler()


def test_yazilan_belge_icerigi_yol_hafizasina_girmez(tmp_path):
    """04.11: write_file ile yazılan belgenin tamamı ipucunda modele geri gidiyordu."""
    uzun = "# FENIX Tanıtım\n" + "Bu satır belgenin içeriği. " * 200
    yh.ogren('Masaüstüne "FENIX_Tanitim.docx" adlı bir Word belgesi oluştur, kendini anlat',
             [("search_web", {"query": "copilot özellikleri"}, {"status": "ok"}),
              ("write_file", {"path": "FENIX_Tanitim.docx", "content": uzun}, {"status": "ok"})])
    metin, _ = yh.ipucu('Masaüstüne "FENIX_Kapsamli.docx" adlı bir Word belgesi oluştur, kendini anlat')
    assert "belgenin içeriği" not in metin and len(metin) < 1500
    assert "<içerik>" in metin
