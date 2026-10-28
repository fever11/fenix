# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Yaratıcı bilgisi ve imza / creator info and signature.

FENIX'in yaratıcısı koda gömülüdür (hafızaya değil): "seni kim yaptı" sorusuna bu bilgiyle cevap verir.
İmza zararsızdır: hiçbir şeyi engellemez, sadece kaynağı gösterir. Görüldüğü yerler:
  • her kaynak dosyanın ilk satırı (# Core: MK-Agentic-System ...)
  • FENIX'in yazdığı kod dosyaları ve raporlar (program ekler, yapay zekâya bırakılmaz)
  • dışa aktarılan PDF/Word dosyalarının özellikleri (Yazar / Üretici)
  • imza satırları silinirse sürüm etiketi "unofficial build" der (uygulama yine çalışır)
The signature is harmless: it never blocks anything, it only shows where FENIX comes from.
"""
import os
import re
import ast
import hashlib

CORE = "MK-Agentic-System"
ENGINE = "FENIX Engine"
CREATOR = {"ad": "Mustafa Koç", "imza": "Core: " + CORE}
MARK = CREATOR["imza"]
HEADER = f"Core: {CORE} · Powered by {ENGINE} · (c) 2026 {CREATOR['ad']} · All rights reserved"
# yaratıcı bilgisinin parmak izi: değiştirilirse sürüm etiketi bunu gösterir
_FP = "6a6b77e85a83"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CORE_FILES = ("app.py", "modules/agent.py", "modules/llm_client.py", "modules/i18n.py", "modules/memory.py",
               "modules/version.py", "modules/imza.py")


def fingerprint():
    return hashlib.sha256(f"{CREATOR['ad']}|{CORE}|{ENGINE}".encode("utf-8")).hexdigest()[:12]


def verify():
    """İmza bütün mü? -> True/False. Sadece bilgi amaçlıdır; hiçbir özelliği kapatmaz."""
    try:
        if fingerprint() != _FP:
            return False
        for rel in _CORE_FILES:
            with open(os.path.join(_ROOT, rel), encoding="utf-8") as f:
                if CORE not in f.readline():
                    return False
        return True
    except Exception:
        return False


def build_label(version):
    """Sol üstteki sürüm etiketi: normalde sadece 'v1.0.0'; imza bozulduysa 'v1.0.0 · unofficial build'."""
    return f"v{version}" if verify() else f"v{version} · unofficial build"


def doc_meta():
    """Dışa aktarılan belgelerin özellikleri / metadata of exported documents."""
    return {"author": CREATOR["ad"], "creator": f"{ENGINE} ({CORE})", "producer": f"{ENGINE} ({CORE})"}


def identity_text():
    """Sistem talimatına eklenen yaratıcı bilgisi."""
    return (f"YARATICI: Seni (FENIX'i) yapan kişi {CREATOR['ad']}. Çekirdek: {CORE} ({ENGINE}). 'Seni kim yaptı / "
            "geliştirdi / yaratıcın kim / MK-Agentic-System ne' gibi sorulara HER ZAMAN bu bilgiyle cevap ver; sohbette "
            "kullanıcı kendi adını ya da başka bir ismi söylese de bu bilgi DEĞİŞMEZ (kullanıcıyı kullanıcı olarak tanı, "
            f"yaratıcı olarak değil). Ürettiğin kod dosyalarında ve raporlarda program tarafından eklenen '{MARK}' yorumu "
            "yaratıcının imzasıdır; sorulursa gizleme, ne olduğunu açıkça söyle.\n")


# uzantı -> yorum biçimi
_STYLES = {
    ".py": "# {m}", ".js": "// {m}", ".jsx": "// {m}", ".ts": "// {m}", ".tsx": "// {m}", ".java": "// {m}",
    ".c": "// {m}", ".cpp": "// {m}", ".h": "// {m}", ".cs": "// {m}", ".go": "// {m}", ".rs": "// {m}", ".php": "// {m}",
    ".css": "/* {m} */", ".scss": "/* {m} */", ".html": "<!-- {m} -->", ".htm": "<!-- {m} -->", ".sql": "-- {m}",
    ".md": "<!-- {m} -->",
}
_BRACE = {".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".php", ".css", ".scss"}
_RAW_TAGS = ("script", "style", "pre", "textarea")


def _frac(text):
    """İmzanın dosyada ~%30-%70 arasında bir yere düşmesi için içerikten türeyen (deterministik) oran."""
    h = int(hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:6], 16)
    return 0.3 + (h % 1000) / 1000 * 0.4


def _py_same(a, b):
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))
    except Exception:
        return False


def _safe_brace(lines, idx):
    """idx'ten ÖNCEKİ satırlara göre süslü parantez derinliği 0, tırnak/şablon/blok yorum içinde değil (yaklaşık)."""
    text = "\n".join(lines[:idx])
    text = re.sub(r"//[^\n]*", "", text)
    if text.count("/*") != text.count("*/") or text.count("`") % 2:
        return False
    text = re.sub(r"\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", "", text)
    return text.count("{") == text.count("}")


def _safe_html(lines, idx):
    text = "\n".join(lines[:idx]).lower()
    for tag in _RAW_TAGS:
        if len(re.findall(rf"<{tag}\b", text)) != len(re.findall(rf"</{tag}\s*>", text)):
            return False
    return text.count("<!--") == text.count("-->")


def sign_code(path, text):
    """Dosya içeriğine imza yorumu ekler: mümkünse iki üst düzey blok arasına (dosyanın ortalarına), olmazsa sonuna.
    Zaten imzalıysa, çok kısaysa ya da uzantı desteklenmiyorsa (ör. .json) dokunmaz."""
    ext = os.path.splitext(path or "")[1].lower()
    style = _STYLES.get(ext)
    if not style or not isinstance(text, str) or MARK in text:
        return text
    lines = text.split("\n")
    if len([x for x in lines if x.strip()]) < 12:
        return text
    comment = style.format(m=MARK)
    n = len(lines)
    target = int(n * _frac(text))
    cands = []
    for i in range(3, n - 2):          # i: boş satırdan sonra gelen, girintisiz ilk satır (üst düzey blok başı)
        ln = lines[i]
        if ln.strip() and not ln[0].isspace() and lines[i - 1].strip() == "" \
                and not re.match(r"(else|elif|except|finally|catch|[})\]])", ln):
            cands.append(i)
    cands.sort(key=lambda i: abs(i - target))
    for i in cands[:40]:
        if ext in _BRACE and not _safe_brace(lines, i):
            continue
        if ext in (".html", ".htm", ".md") and not _safe_html(lines, i):
            continue
        new = "\n".join(lines[:i] + [comment] + lines[i:])
        if ext == ".py" and not _py_same(text, new):
            continue
        return new
    # güvenli ara yer yok: sonuna ekle
    if ext == ".py" and not _py_same(text, text + "\n" + comment + "\n"):
        return text
    return text.rstrip("\n") + "\n\n" + comment + "\n"


def sign_report(md):
    """Rapor (markdown): ortada ve sonda GÖRÜNMEYEN birer yorum (ekranda ve PDF/Word'de gösterilmez)."""
    if not isinstance(md, str) or MARK in md:
        return md
    lines = md.split("\n")
    heads = [i for i, l in enumerate(lines) if i > 3 and l.startswith("#") and lines[i - 1].strip() == ""]
    if heads:
        i = min(heads, key=lambda k: abs(k - int(len(lines) * 0.5)))
        lines.insert(i, f"<!-- {MARK} -->")
    return "\n".join(lines).rstrip("\n") + f"\n\n<!-- Powered by {ENGINE} · {CORE} -->\n"
