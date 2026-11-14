# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Bölüm bölüm uzun belge yazıcı (v1.4, Mustafa'nın isteği).

"Ders notu kaynak miktarına göre uzamalı, hiçbir kaynak atlanmamalı, eksik hissettirmemeli."
Tek seferde uzun belge yazdırmak iki yüzden olmuyor: Groq'un ücretsiz katmanı dakikada ~8 bin token kabul ediyor ve
model uzun çıktıyı kendiliğinden kısaltıyor. Bu modül işi böler:
  1) Kaynaklar (ekli PDF/Word/metin) ~5.000 karakterlik parçalara ayrılır ve numaralanır.
  2) İçerik planı çıkarılır: bölüm sayısı kaynak miktarına göre belirlenir; HER parça bir bölüme atanır
     (plan bir parçayı unutursa kod onu en yakın bölüme ekler). Kaynak yoksa konunun kapsamına göre 7-10 bölüm.
  3) Her bölüm ayrı bir istekle, yalnızca kendi kaynak parçalarıyla yazılır (istekler dakika sınırının altında kalır).
  4) Sonda "Kendini dene" soruları ve özet; "Kaynaklar" bölümünde hangi dosyanın hangi bölümlerde kullanıldığı yazılır.
  5) Belge yapı taşlarıyla (kutular, tablolar, tema) Word/PDF olarak kaydedilir ve işlem defterine yazılır.
"""
import json
import math
import os
import re

PARCA_KARAKTER = 5000          # bir kaynak parçası (~1.300 token)
BOLUM_KAYNAK_SINIRI = 11000    # bir bölüm isteğine konan en fazla kaynak metni
EN_AZ_BOLUM, EN_COK_BOLUM = 6, 30

DERS_NOTU_RE = re.compile(r"ders not|çalışma not|konu anlatım|not(lar)?(ı)? (çıkar|hazırla|oluştur|yaz)|"
                          r"(kapsamlı|detaylı|ayrıntılı|uzun) (bir )?(not|belge|rapor|döküman|doküman)|"
                          r"sınav(a| için) (çalışma )?not|özet not|ders özeti", re.IGNORECASE)
DOSYA_RE = re.compile(r"([\w\-.ğüşıöçĞÜŞİÖÇ]+\.(?:pdf|docx))\b", re.IGNORECASE)

SISTEM = ("Sen titiz bir öğretmen ve teknik yazarsın. Türkçe, akıcı, eksiksiz ve öğretici belgeler yazarsın. "
          "Uydurmazsın: emin olmadığın bilgiyi 'tahminim/doğrulamadım' diye belirtir ya da '::: tahmin' kutusuna "
          "koyarsın; okumadığın bir kaynağı göstermezsin.")
YAPI_TASLARI = ("Markdown yaz. Kullanabileceğin yapı taşları ('::: tür isteğe bağlı başlık' ile açılır, ayrı satırda "
                "':::' ile kapanır): tanim, ornek, ipucu, uyari, formul, soru (satırlar 'S: …' / 'C: …'), adim (her satır "
                "bir adım), not, alinti, tahmin. Ayrıca ### alt başlık, | tablo |, - madde, **kalın**. İçeriğe uygun "
                "olanları seç; sadece madde listesi bırakma, kavramları açıkla.")


def istek_mi(metin, ekler=None):
    """Bu istek bölüm bölüm yazılacak bir belge mi? (ders notu / kapsamlı belge, dosya ya da ek ile)"""
    t = metin or ""
    if not DERS_NOTU_RE.search(t):
        return False
    return bool(ekler) or bool(DOSYA_RE.search(t)) or bool(re.search(r"\b(pdf|word|docx)\b", t, re.IGNORECASE))


def hedef_dosya(metin, baslik):
    m = DOSYA_RE.search(metin or "")
    if m:
        return m.group(1).strip()
    uzanti = ".docx" if re.search(r"\b(word|docx)\b", metin or "", re.IGNORECASE) else ".pdf"
    ad = re.sub(r"[^\w\-ğüşıöçĞÜŞİÖÇ ]+", "", baslik or "ders notu").strip()[:60] or "ders notu"
    return ad + uzanti


def parcala(kaynaklar, boyut=PARCA_KARAKTER):
    """[{'ad','metin'}] -> [{'id','ad','metin'}]; paragraf sınırlarından bölünür."""
    parcalar = []
    for k in kaynaklar:
        metin = (k.get("metin") or "").strip()
        if not metin:
            continue
        paragraflar, buf = re.split(r"\n\s*\n", metin), ""
        for p in paragraflar:
            while len(p) > boyut:                    # tek paragraf çok uzunsa zorla böl
                if buf:
                    parcalar.append((k["ad"], buf))
                    buf = ""
                parcalar.append((k["ad"], p[:boyut]))
                p = p[boyut:]
            if len(buf) + len(p) + 2 > boyut and buf:
                parcalar.append((k["ad"], buf))
                buf = ""
            buf = (buf + "\n\n" + p).strip()
        if buf:
            parcalar.append((k["ad"], buf))
    return [{"id": f"P{i}", "ad": ad, "metin": m} for i, (ad, m) in enumerate(parcalar, 1)]


def bolum_sayisi(parcalar):
    if not parcalar:
        return 8
    toplam = sum(len(p["metin"]) for p in parcalar)
    return max(EN_AZ_BOLUM, min(EN_COK_BOLUM, math.ceil(toplam / 7000)))


def _json(metin):
    m = re.search(r"\{.*\}", metin or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def plani_duzelt(plan, parcalar, n):
    """Planı doğrular: her parça en az bir bölüme atanır (unutulan parça önceki parçanın bölümüne eklenir)."""
    bolumler = [b for b in (plan or {}).get("bolumler", []) if isinstance(b, dict) and b.get("baslik")]
    if not bolumler:                                 # plan çıkmadıysa: parçaları sırayla gruplara böl
        if not parcalar:
            return None
        grup = max(1, math.ceil(len(parcalar) / n))
        bolumler = [{"baslik": f"Bölüm {i + 1}", "icerik": "",
                     "parcalar": [p["id"] for p in parcalar[i * grup:(i + 1) * grup]]}
                    for i in range(math.ceil(len(parcalar) / grup))]
    gecerli = {p["id"] for p in parcalar}
    for b in bolumler:
        b["parcalar"] = [str(x) for x in (b.get("parcalar") or []) if str(x) in gecerli]
    atanan = {x for b in bolumler for x in b["parcalar"]}
    for i, p in enumerate(parcalar):
        if p["id"] in atanan:
            continue
        hedef = bolumler[-1]
        for b in bolumler:                           # bir önceki parçanın bölümüne koy (konu sırası korunsun)
            if i > 0 and parcalar[i - 1]["id"] in b["parcalar"]:
                hedef = b
        hedef["parcalar"].append(p["id"])
    plan = dict(plan or {})
    plan["bolumler"] = bolumler
    return plan


def olustur(llm, mode_cfg, istek, kaynaklar=None, ilerleme=None):
    """-> {'status', 'md', 'baslik', 'dosya', 'bolum', 'parca'}"""
    ilerleme = ilerleme or (lambda m: None)
    parcalar = parcala(kaynaklar or [])
    n = bolum_sayisi(parcalar)
    ilerleme(f"belge planlanıyor ({len(parcalar)} kaynak parçası, ~{n} bölüm)")
    ozetler = "\n".join(f"{p['id']} [{p['ad']}]: {p['metin'][:280].replace(chr(10), ' ')}…" for p in parcalar)
    plan_istek = (
        f"KULLANICININ İSTEĞİ: {istek}\n\n"
        + (f"KAYNAK PARÇALARI ({len(parcalar)} adet; her birinin başı):\n{ozetler}\n\n" if parcalar else
           "Kaynak verilmedi; konuyu kendi bilginle, bir ders kitabı bölümü kadar kapsamlı planla.\n\n")
        + f"Bu istek için {n} civarı bölümlük (en az {EN_AZ_BOLUM}) bir belge planı çıkar. Bölümler mantıklı bir "
          "öğrenme sırasında olsun. " + ("HER kaynak parçası en az bir bölüme atanmalı; hiçbir parça dışarıda "
                                         "kalmamalı. " if parcalar else "")
        + 'SADECE JSON döndür: {"baslik": "belge başlığı", "tema": "mavi|yesil|mor|turuncu|kirmizi|lacivert|turkuaz|'
          'gri|pembe", "giris": "2-3 cümlelik giriş", "bolumler": [{"baslik": "...", "icerik": "bu bölümde '
          'anlatılacak ana noktalar", "parcalar": ["P1", "P2"]}]}')
    plan = _json(llm.complete(mode_cfg, plan_istek, system=SISTEM, temperature=0.3, gemini_fallback=False))
    plan = plani_duzelt(plan, parcalar, n) or {"bolumler": [{"baslik": "Konu", "icerik": istek, "parcalar": []}]}
    baslik = str(plan.get("baslik") or "Ders Notu")[:90]
    tema = str(plan.get("tema") or "mavi").lower()
    bolumler = plan["bolumler"]
    harita = {p["id"]: p for p in parcalar}
    taslak = "\n".join(f"{i}. {b['baslik']}" for i, b in enumerate(bolumler, 1))

    yazilan = []
    for i, b in enumerate(bolumler, 1):
        ilerleme(f"bölüm {i}/{len(bolumler)} yazılıyor: {b['baslik']}")
        kaynak = "\n\n".join(f"--- {harita[x]['id']} ({harita[x]['ad']}) ---\n{harita[x]['metin']}"
                             for x in b["parcalar"] if x in harita)
        # Bölümün kaynağı çok büyükse kendi içinde parça parça yazılır (hiçbir şey kesilmesin)
        dilimler = [kaynak[j:j + BOLUM_KAYNAK_SINIRI] for j in range(0, len(kaynak), BOLUM_KAYNAK_SINIRI)] or [""]
        parcalar_md = []
        for d, dilim in enumerate(dilimler, 1):
            devam = d > 1
            prompt = (
                f"BELGE: {baslik}\nKULLANICININ İSTEĞİ: {istek}\nBELGENİN BÖLÜMLERİ:\n{taslak}\n\n"
                f"ŞİMDİ YAZILACAK BÖLÜM: {i}. {b['baslik']}" + (f" (devamı, {d}. kısım)" if devam else "") + "\n"
                f"Bu bölümde anlatılacaklar: {b.get('icerik') or b['baslik']}\n\n"
                + (f"KAYNAK METİN (bu bölümün kaynağı; içindeki HER önemli bilgiyi belgeye aktar, atlama):\n{dilim}\n\n"
                   if dilim else "Kaynak yok: konuyu kendi bilginle eksiksiz anlat.\n\n")
                + YAPI_TASLARI + "\n"
                + (f"'## {b['baslik']}' başlığıyla başla. " if not devam else "Başlık yazma, önceki kısmın devamını yaz. ")
                + "Bu bölüm kapsamlı olsun: açıklama paragrafları + uygun kutular/tablolar/örnekler. Diğer bölümlerin "
                  "konularını tekrar etme. Belge başlığı, giriş ya da genel özet yazma; sadece bu bölümü yaz.")
            parcalar_md.append((llm.complete(mode_cfg, prompt, system=SISTEM, temperature=0.4,
                                             gemini_fallback=False) or "").strip())
        metin = "\n\n".join(x for x in parcalar_md if x)
        if not re.match(r"^##\s", metin):
            metin = f"## {b['baslik']}\n\n" + metin
        yazilan.append(metin)

    ilerleme("'Kendini dene' soruları ve özet yazılıyor")
    ozet_kaynak = "\n\n".join(m[:1500] for m in yazilan)[:12000]
    son = (llm.complete(mode_cfg, (
        f"BELGE: {baslik}\nAşağıda belgenin bölümlerinin başları var:\n{ozet_kaynak}\n\n"
        "Belgenin sonuna iki bölüm yaz:\n## Kendini Dene\n(::: soru kutusunda, bölümlerin hepsini kapsayan 8-12 soru; "
        "'S: …' / 'C: …' satırları)\n## Özet\n(::: ozet kutusunda, her bölümden 1-2 maddelik toparlama)\n"
        + YAPI_TASLARI), system=SISTEM, temperature=0.3, gemini_fallback=False) or "").strip()

    kaynaklar_md = ""
    if parcalar:
        kullanim = {}
        for i, b in enumerate(bolumler, 1):
            for x in b["parcalar"]:
                if x in harita:
                    kullanim.setdefault(harita[x]["ad"], set()).add(i)
        kaynaklar_md = "## Kaynaklar\n" + "\n".join(
            f"- {ad} (kullanıldığı bölümler: {', '.join(str(i) for i in sorted(bs))})" for ad, bs in kullanim.items())
    md = (f"<!-- tema: {tema} -->\n# {baslik}\n\n{plan.get('giris') or ''}\n\n" + "\n\n".join(yazilan)
          + (f"\n\n{son}" if son else "") + (f"\n\n{kaynaklar_md}" if kaynaklar_md else ""))
    return {"status": "ok", "md": md, "baslik": baslik, "bolum": len(bolumler), "parca": len(parcalar)}
