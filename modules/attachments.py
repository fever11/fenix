# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Dosya Ekleri
------------
Uygulamaya eklenen dosyaları okur ve modele verilecek hale getirir.

Desteklenenler:
- PDF (.pdf)                  -> sayfa sayfa metin (pypdf)
- Word (.docx)                -> paragraflar + tablolar (python-docx)
- Excel (.xlsx, .xlsm)        -> her sayfa CSV benzeri satırlar (openpyxl)
- CSV / TSV
- Düz metin ve kod            -> .txt .md .py .js .ts .json .html .css .yaml .sql ...
- Resim (.png .jpg .webp ...) -> küçültülmüş JPEG (görüntü modeline gider)

Not: Taranmış (resim) PDF'lerde metin katmanı olmadığı için metin çıkmaz; bu durumda
kullanıcıya bildirilir.
"""
import io
import os
import csv
import base64

MAX_FILE_MB = 25
MAX_ROWS_PER_SHEET = 2000

TEXT_EXT = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".htm", ".css", ".scss",
            ".yaml", ".yml", ".xml", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".php", ".rb",
            ".kt", ".swift", ".sql", ".log", ".ini", ".cfg", ".toml", ".env", ".bat", ".ps1", ".sh", ".vue",
            ".svelte", ".dart", ".lua", ".r", ".m", ".tex", ".srt", ".gitignore"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
SUPPORTED = TEXT_EXT | IMAGE_EXT | {".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".tsv"}

FILETYPES = [
    ("Desteklenen dosyalar", " ".join(f"*{e}" for e in sorted(SUPPORTED))),
    ("Belgeler", "*.pdf *.docx *.txt *.md"),
    ("Tablolar", "*.xlsx *.xlsm *.csv *.tsv"),
    ("Kod", "*.py *.js *.ts *.tsx *.jsx *.json *.html *.css *.java *.cs *.cpp *.go *.sql"),
    ("Resimler", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
    ("Tüm dosyalar", "*.*"),
]


class AttachmentError(Exception):
    pass


def _need(module, pip_name):
    try:
        return __import__(module)
    except ImportError:
        raise AttachmentError(f"Bu dosya türü için '{pip_name}' paketi gerekli. Komut: pip install {pip_name}")


def _read_text_file(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def _read_pdf(path):
    pypdf = _need("pypdf", "pypdf")
    reader = pypdf.PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise AttachmentError("PDF şifreli, açılamadı.")
    parts = []
    for i, page in enumerate(reader.pages, 1):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(f"--- Sayfa {i} ---\n{t.strip()}")
    pages = len(reader.pages)
    text = "\n\n".join(parts)
    note = ""
    if not text.strip():
        note = "PDF'te metin katmanı yok (taranmış belge olabilir); metin çıkarılamadı."
    return text, f"{pages} sayfa", note


def _read_docx(path):
    docx = _need("docx", "python-docx")
    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for ti, table in enumerate(d.tables, 1):
        parts.append(f"--- Tablo {ti} ---")
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts), f"{len(d.paragraphs)} paragraf, {len(d.tables)} tablo", ""


def _read_xlsx(path):
    openpyxl = _need("openpyxl", "openpyxl")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    parts, info = [], []
    for ws in wb.worksheets:
        parts.append(f"--- Sayfa: {ws.title} ---")
        n = 0
        for row in ws.iter_rows(values_only=True):
            if all(v is None for v in row):
                continue
            parts.append(";".join("" if v is None else str(v) for v in row))
            n += 1
            if n >= MAX_ROWS_PER_SHEET:
                parts.append(f"(… ilk {MAX_ROWS_PER_SHEET} satır alındı)")
                break
        info.append(f"{ws.title}: {n} satır")
    wb.close()
    return "\n".join(parts), ", ".join(info), ""


def _read_csv(path, delimiter=None):
    text = _read_text_file(path)
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:5000], delimiters=",;\t|").delimiter
        except Exception:
            delimiter = ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    out = [";".join(r) for r in rows[:MAX_ROWS_PER_SHEET]]
    if len(rows) > MAX_ROWS_PER_SHEET:
        out.append(f"(… ilk {MAX_ROWS_PER_SHEET} satır alındı, toplam {len(rows)})")
    return "\n".join(out), f"{len(rows)} satır", ""


def _read_image(path):
    from PIL import Image
    img = Image.open(path)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), f"{img.width}x{img.height}"


def load(path):
    """Dosyayı okuyup ek sözlüğü döner:
    {name, path, ext, kind: 'text'|'image', text, image_b64, info, note, chars, size}"""
    if not os.path.isfile(path):
        raise AttachmentError("Dosya bulunamadı.")
    size = os.path.getsize(path)
    if size > MAX_FILE_MB * 1024 * 1024:
        raise AttachmentError(f"Dosya çok büyük ({size / 1024 / 1024:.1f} MB). Sınır {MAX_FILE_MB} MB.")
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower() or name.lower()
    item = {"name": name, "path": path, "ext": ext, "size": size, "kind": "text",
            "text": "", "image_b64": None, "info": "", "note": ""}
    if ext in IMAGE_EXT:
        item["kind"] = "image"
        item["image_b64"], item["info"] = _read_image(path)
    elif ext == ".pdf":
        item["text"], item["info"], item["note"] = _read_pdf(path)
    elif ext == ".docx":
        item["text"], item["info"], item["note"] = _read_docx(path)
    elif ext in (".xlsx", ".xlsm"):
        item["text"], item["info"], item["note"] = _read_xlsx(path)
    elif ext in (".csv", ".tsv"):
        item["text"], item["info"], item["note"] = _read_csv(path, "\t" if ext == ".tsv" else None)
    elif ext in TEXT_EXT or size < 2 * 1024 * 1024:
        text = _read_text_file(path)
        if "\x00" in text[:2000]:
            raise AttachmentError("Bu dosya ikili (binary) görünüyor; okunabilir metin içermiyor.")
        item["text"], item["info"] = text, f"{text.count(chr(10)) + 1} satır"
    else:
        raise AttachmentError(f"'{ext}' türü desteklenmiyor.")
    item["chars"] = len(item["text"])
    return item


def label(item):
    icon = {"image": "🖼"}.get(item["kind"], "📄")
    return f"{icon} {item['name']}" + (f" ({item['info']})" if item.get("info") else "")


def chunk_text(text, size=8000, overlap=300):
    """Uzun metni parçalara böler (satır/paragraf sınırlarına yakın keser)."""
    chunks, i, n = [], 0, len(text)
    while i < n:
        end = min(n, i + size)
        if end < n:
            cut = text.rfind("\n", i + size // 2, end)
            end = cut if cut > 0 else end
        chunks.append(text[i:end])
        if end >= n:
            break
        i = max(end - overlap, i + 1)
    return chunks
