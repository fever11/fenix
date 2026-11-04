# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Lisans: GPL-3.0'ın resmi metni + ek şartlar (atıf, köken, ad); dağıtılan her dosyada GPL başlığı var."""
import hashlib
import os

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Sadece özel sürümde olan, dağıtılmayan dosyalar (.gitignore'da): onlar 'Tüm hakları saklıdır' kalır
OZEL = {"modules/lab.py", "modules/lab_nvidia.py", "modules/saglayicilar.py", "modules/ogrenme.py",
        "scripts/import_jarvis.py", "Import_JARVIS.bat", "docs/OZEL_SURUM.md", "scripts/kanit_testi.py",
        "scripts/kanit_seti.py", "Kanit_Testi.bat", "scripts/ogrenme_deneyi.py", "scripts/egitim_seti.py",
        "Ogrenme_Deneyi.bat", "scripts/hiz_deneyi.py", "Hiz_Deneyi.bat"}


def _oku(rel):
    with open(os.path.join(KOK, rel), encoding="utf-8") as f:
        return f.read()


def test_lisans_gpl3_resmi_metni():
    with open(os.path.join(KOK, "LICENSE"), "rb") as f:
        assert hashlib.md5(f.read()).hexdigest() == "1ebbd3e34237af26da5dc08a4e440464"   # GNU'nun gpl-3.0.txt'si


def test_ek_sartlar_ve_atif():
    n = _oku("NOTICE.md")
    assert "GPL-3.0-only" in n and "Mustafa Koç" in n and "github.com/fever11/fenix" in n
    for madde in ("(7b)", "(7c)", "(7e)"):
        assert madde in n
    assert "Based on FENIX by Mustafa Koç" in n


def test_dagitilan_dosyalarda_gpl_basligi_var_tum_haklari_saklidir_yok():
    eksik, eski = [], []
    for dp, dn, fn in os.walk(KOK):
        dn[:] = [d for d in dn if d not in ("__pycache__", "data", ".git", "venv", ".pytest_cache")]
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), KOK).replace("\\", "/")
            if rel in OZEL or not f.endswith((".py", ".bat", ".vbs", ".ps1")):
                continue
            s = _oku(rel)
            if "All rights " + "reserved" in s:          # (bu test dosyası kendini yakalamasın)
                eski.append(rel)
            if "Core: MK-Agentic-System" in s.splitlines()[0] if s else False:
                if "GPL-3.0" not in s.splitlines()[0]:
                    eksik.append(rel)
    assert not eski, f"'Tüm hakları saklıdır' kalmış: {eski}"
    assert not eksik, f"GPL başlığı eksik: {eksik}"
