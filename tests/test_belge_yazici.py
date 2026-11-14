# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Bölüm bölüm, kaynak miktarına göre uzayan belge yazıcı (v1.4)."""
import json

from modules import belge_yazici as B


def _kaynak(n_paragraf, ad="biyoloji.pdf"):
    return {"ad": ad, "metin": "\n\n".join(f"Paragraf {i}: " + "fotosentez klorofil " * 60 for i in range(n_paragraf))}


def test_istek_algilama():
    assert B.istek_mi("bu PDF'ten ders notu çıkar", ekler=[{"name": "a.pdf"}])
    assert B.istek_mi("fotosentez hakkında kapsamlı bir ders notu hazırla fotosentez.pdf olarak kaydet")
    assert B.istek_mi("döngüler konusunda word olarak ders notu yaz")
    assert not B.istek_mi("ders notu nedir")                      # dosya/ek yok: sohbet
    assert not B.istek_mi("masaüstüne not.txt yaz")
    assert not B.istek_mi("bu pdf'i özetle", ekler=[{"name": "a.pdf"}])


def test_hedef_dosya():
    assert B.hedef_dosya("ders notu çıkar donguler.docx olsun", "X") == "donguler.docx"
    assert B.hedef_dosya("word olarak ders notu", "Döngüler: Giriş") == "Döngüler Giriş.docx"
    assert B.hedef_dosya("pdf ders notu", "") == "ders notu.pdf"


def test_parcalar_hicbir_metni_kaybetmez():
    k = _kaynak(40)
    p = B.parcala([k, {"ad": "bos.txt", "metin": "  "}])
    assert len(p) > 3 and all(len(x["metin"]) <= B.PARCA_KARAKTER for x in p)
    sade = lambda t: "".join(t.split())
    assert sade("".join(x["metin"] for x in p)) == sade(k["metin"])
    assert [x["id"] for x in p] == [f"P{i}" for i in range(1, len(p) + 1)]


def test_bolum_sayisi_kaynakla_buyur():
    az, cok = B.parcala([_kaynak(10)]), B.parcala([_kaynak(200)])
    assert B.bolum_sayisi([]) == 8
    assert B.bolum_sayisi(az) == B.EN_AZ_BOLUM
    assert B.EN_AZ_BOLUM < B.bolum_sayisi(cok) <= B.EN_COK_BOLUM


def test_plan_unutulan_parcayi_ekler():
    p = B.parcala([_kaynak(40)])
    plan = {"bolumler": [{"baslik": "A", "parcalar": ["P1", "P99"]}, {"baslik": "B", "parcalar": [p[-1]["id"]]}]}
    d = B.plani_duzelt(plan, p, 6)
    atanan = [x for b in d["bolumler"] for x in b["parcalar"]]
    assert set(atanan) == {x["id"] for x in p} and "P99" not in atanan
    assert d["bolumler"][0]["parcalar"][:2] == ["P1", "P2"]        # sıra korunur: P2, P1'in bölümüne


def test_plan_bozuksa_parcalar_sirayla_gruplanir():
    p = B.parcala([_kaynak(40)])
    d = B.plani_duzelt(None, p, 3)
    assert len(d["bolumler"]) <= 3 and sum(len(b["parcalar"]) for b in d["bolumler"]) == len(p)


class _SahteLLM:
    def __init__(self):
        self.istekler = []

    def complete(self, mode_cfg, prompt, system=None, **kw):
        self.istekler.append(prompt)
        if "SADECE JSON" in prompt:
            ids = [l.split(" ")[0] for l in prompt.splitlines() if l.startswith("P")]
            return "Plan:\n" + json.dumps({"baslik": "Fotosentez", "tema": "yesil", "giris": "Giriş.",
                                          "bolumler": [{"baslik": "Işık evresi", "icerik": "x", "parcalar": ids[:1]},
                                                       {"baslik": "Calvin döngüsü", "icerik": "y", "parcalar": []}]})
        if "Kendini Dene" in prompt:
            return "## Kendini Dene\n::: soru\nS: ?\nC: !\n:::\n## Özet\n::: ozet\n- a\n:::"
        return "Bölüm metni ::: tanim Klorofil\nYeşil pigment.\n:::"


def test_uctan_uca_tum_kaynaklar_kullanilir():
    llm, notlar = _SahteLLM(), []
    r = B.olustur(llm, {}, "bu pdf'ten ders notu çıkar", [_kaynak(40)], ilerleme=notlar.append)
    md = r["md"]
    assert md.startswith("<!-- tema: yesil -->\n# Fotosentez")
    assert "## Işık evresi" in md and "## Calvin döngüsü" in md and "## Kendini Dene" in md
    assert "## Kaynaklar" in md and "biyoloji.pdf (kullanıldığı bölümler:" in md
    # plan sadece P1'i atadı; geri kalan her parça yine de bir bölüm isteğinde modele verildi
    bolum_istekleri = "\n".join(x for x in llm.istekler if "ŞİMDİ YAZILACAK BÖLÜM" in x)
    assert all(f"--- {p['id']} " in bolum_istekleri for p in B.parcala([_kaynak(40)]))
    assert any("bölüm 1/" in n for n in notlar)
    # tek istekte kaynak sınırı aşılmaz (dakikalık token sınırı)
    assert all(len(x) < B.BOLUM_KAYNAK_SINIRI + 4000 for x in llm.istekler)


def test_kaynaksiz_belge():
    r = B.olustur(_SahteLLM(), {}, "döngüler hakkında kapsamlı ders notu yaz pdf")
    assert r["parca"] == 0 and "## Kaynaklar" not in r["md"] and r["bolum"] >= 2
