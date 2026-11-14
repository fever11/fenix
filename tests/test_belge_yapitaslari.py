# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Belge yapı taşları ve tema (v1.4): sabit şablon yok, model içeriğe göre yapı taşlarını seçer."""
import os

import pytest

from modules import functions as fx
from modules import report_export as R

ORNEK = """<!-- tema: yesil -->
# Fotosentez – Ders Notu
Giriş paragrafı **kalın** kelimeyle.

::: tanim Fotosentez
Işık enerjisiyle glikoz üretimi.
:::

## Denklem
::: formul
6CO₂ + 6H₂O + ışık → C₆H₁₂O₆ + 6O₂
:::

| Evre | Yer |
|---|---|
| Işığa bağımlı | Tilakoit |

::: soru
S: Calvin döngüsü nerede?
C: Stromada.
:::

::: adim Deney
Bitkiyi ışığa koy.
Kabarcıkları say.
:::

> Bilim bir merak işidir.

::: Uyarı
Fotosentez ile solunumu karıştırma.
:::
"""


def test_yapi_taslari_ayristirilir():
    y = R._lines_struct(ORNEK)
    turler = [c[0] for k, c in y if k == "blok"]
    assert turler == ["tanim", "formul", "soru", "adim", "uyari"]       # 'Uyarı' eşanlamlısı tanınır
    assert ("quote", "Bilim bir merak işidir.") in y
    tanim = next(c for k, c in y if k == "blok")
    assert tanim[1] == "Fotosentez" and tanim[2] == ["Işık enerjisiyle glikoz üretimi."]


def test_tema_rengi():
    assert R.tema_rengi(ORNEK) == R.TEMALAR["yesil"]
    assert R.tema_rengi("<!-- tema: Kırmızı -->") == R.TEMALAR["kirmizi"]
    assert R.tema_rengi("# başlık") == R.TEMALAR["mavi"]
    assert R.tema_rengi("<!-- tema: fosforlu -->") == R.TEMALAR["mavi"]


def test_bilinmeyen_blok_not_olur():
    y = R._lines_struct("::: garip\nmetin\n:::")
    assert y[0] == ("blok", ("not", "", ["metin"]))


def test_kapanmamis_blok_cokmez():
    y = R._lines_struct("::: tanim\nmetin\nbaşka")
    assert y[0][0] == "blok" and y[0][1][2] == ["metin", "başka"]


@pytest.mark.parametrize("uzanti", [".pdf", ".docx"])
def test_belge_uretilir(tmp_path, uzanti):
    yol = str(tmp_path / ("not" + uzanti))
    (R.export_pdf if uzanti == ".pdf" else R.export_docx)(ORNEK, yol)
    assert os.path.getsize(yol) > 2000


def test_docx_kutu_ve_baslik(tmp_path):
    from docx import Document
    yol = str(tmp_path / "not.docx")
    R.export_docx(ORNEK, yol)
    d = Document(yol)
    metin = "\n".join(p.text for p in d.paragraphs)
    kutular = "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    assert "Fotosentez – Ders Notu" in metin                   # ilk # başlık belge başlığı oldu
    assert "Tanım: Fotosentez" in kutular and "Dikkat" in kutular and "1. Bitkiyi ışığa koy." in kutular


def test_kaynaksiz_belgeye_durust_not_eklenir(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    yakalanan = {}
    monkeypatch.setattr(R, "export_docx", lambda md, p: (yakalanan.setdefault("md", md), open(p, "wb").write(b"x")))
    fx.write_file(str(tmp_path / "a.docx"), "# Başlık\nmetin")
    assert "Kaynak gösterilmeyen bilgileri" in yakalanan["md"]
    yakalanan.clear()
    fx.write_file(str(tmp_path / "b.docx"), "# Başlık\nmetin\n## Kaynaklar\n- https://ornek.org")
    assert "Kaynak gösterilmeyen" not in yakalanan["md"]
