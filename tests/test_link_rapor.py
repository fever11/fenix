# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Sahte site tespiti (internete çıkmadan), rapor kuralları ve Word/PDF dışa aktarma."""
import os

import pytest

from modules import audit_rules as ar
from modules import security as sec


@pytest.mark.parametrize("sahte, asil", [("g00gle.com", "google.com"), ("paypa1.com", "paypal.com"),
                                          ("trendyo1.com", "trendyol.com"), ("githuub.com", "github.com")])
def test_benzer_yazimli_sahte_site_yakalanir(sahte, asil):
    assert any(asil == m[1] for m in sec._spoof_matches(sahte)), f"{sahte} yakalanmadı"


@pytest.mark.parametrize("gercek", ["google.com", "google.com.tr", "trendyol.com", "github.com", "garanti.com.tr"])
def test_gercek_site_sahte_sayilmaz(gercek):
    assert sec._spoof_matches(gercek) == []


def test_ayni_sayfanin_farkli_yazimlari_birlesir():
    assert ar.normalize_url("https://ornek.com/index.html?utm_source=x#ust") == ar.normalize_url("https://ornek.com/")


def test_word_ve_pdf_turkce_karakterle_disa_aktarilir():
    from modules import report_export as rx
    md = "# Şirket Güvenlik Raporu\n\n**Önemli:** çğıöşü ÇĞİÖŞÜ\n\n- madde 1\n- madde 2\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    rx.export_docx(md, "rapor.docx", title="Rapor")
    rx.export_pdf(md, "rapor.pdf", title="Rapor")
    assert os.path.getsize("rapor.docx") > 2000 and os.path.getsize("rapor.pdf") > 1000
    from pypdf import PdfReader
    metin = "".join(p.extract_text() or "" for p in PdfReader("rapor.pdf").pages)
    assert "Şirket" in metin and "çğıöşü" in metin


def test_word_ve_pdf_gercek_belge_olarak_yazilir(tmp_path, monkeypatch):
    """04.11 hatası: write_file düz metni .docx diye yazıyordu, Word 'dosya bozuk' diyordu."""
    from modules import functions as fx
    import docx, pypdf
    monkeypatch.setattr(fx, "_confirm", lambda *a, **k: True)      # geçici klasör kullanıcı klasörü dışında
    md = "# FENIX Tanıtım\\n\\n## Yetenekler\\n- Ekran analizi\\n- **Dosya** işlemleri\\n\\n| Mod | İş |\\n|---|---|\\n| Normal | Günlük |"
    w = fx.write_file(str(tmp_path / "FENIX_Tanıtım.docx"), md)
    assert w["status"] == "ok" and w["bicim"] == "docx"
    metin = "\n".join(p.text for p in docx.Document(w["yol"]).paragraphs)
    assert "FENIX Tanıtım" in metin and "Ekran analizi" in metin and "\\n" not in metin
    p = fx.write_file(str(tmp_path / "FENIX_Tanıtım.pdf"), md.replace("\\n", "\n"))
    assert p["status"] == "ok"
    assert "Yetenekler" in pypdf.PdfReader(p["yol"]).pages[0].extract_text()
