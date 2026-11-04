# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Rapor Dışa Aktarma (Word / PDF)
--------------------------------
Raporlarım'daki bir Markdown raporunu .docx ya da .pdf dosyasına çevirir: başlıklar, kalın/kod,
madde/numaralı liste, basit tablo, kaynakça satırları korunur. Hem Word hem PDF aynı satır bazlı
ayrıştırmayı (_lines_struct) ve aynı **kalın**/`kod` tokenleştiricisini (_inline_tokens) kullanır,
böylece ikisi de app.py'deki rapor görüntüleyiciyle (render_markdown) aynı mantıkla biçimlenir.
"""
import re

_INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def _inline_tokens(text):
    """'**kalın** ve `kod`' metnini (parça, tür) ikililerine böler. tür: normal | bold | code."""
    for part in _INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            yield part[2:-2], "bold"
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            yield part[1:-1], "code"
        else:
            yield part, "normal"


def _table_rows(block):
    """Pipe ile ayrılmış tablo satırlarını ayrıklaştırır; ayırıcı satırı (---|---) atar, kısa satırları
    eşit sütun sayısına tamamlar."""
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in block]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c or "--") for c in r)]
    if not cells:
        return []
    ncol = max(len(r) for r in cells)
    return [r + [""] * (ncol - len(r)) for r in cells]


def _lines_struct(md):
    """Markdown'ı (tür, içerik) listesine çevirir. Tür: h1/h2/h3, bullet, numbered, table, muted, src,
    hr, p, blank. app.py'deki render_markdown ile aynı ayrıştırma kurallarını izler."""
    lines = (md or "").splitlines()
    lines = [x for x in lines if not re.fullmatch(r"\s*<!--.*?-->\s*", x)]   # gizli yorumlar (imza) gösterilmez
    out, i, in_sources = [], 0, False
    while i < len(lines):
        line = lines[i]
        st = line.strip()
        if st.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            out.append(("table", block))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", st)
        if m:
            level = min(len(m.group(1)), 3)
            title = m.group(2).replace("**", "")
            in_sources = bool(re.match(r"(kaynak|taranan|referans)", title.lower()))
            out.append((f"h{level}", title))
        elif re.fullmatch(r"-{3,}|\*{3,}|_{3,}", st):
            out.append(("hr", ""))
        elif re.fullmatch(r"_.+_", st):
            out.append(("muted", st.strip("_")))
        elif in_sources and st:
            out.append(("src", st))
        elif re.match(r"^\s*[-*+]\s+", line):
            out.append(("bullet", re.sub(r"^\s*[-*+]\s+", "", line)))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            out.append(("numbered", re.sub(r"^\s*(\d+[.)])\s+", r"\1 ", line.strip())))
        elif st:
            out.append(("p", line))
        else:
            out.append(("blank", ""))
        i += 1
    return out


# ============================= WORD (.docx) =============================
def _docx_add_inline(paragraph, text):
    for chunk, kind in _inline_tokens(text):
        if not chunk:
            continue
        run = paragraph.add_run(chunk)
        if kind == "bold":
            run.bold = True
        elif kind == "code":
            run.font.name = "Consolas"


def export_docx(md, out_path, title=None):
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()
    if title:
        doc.add_heading(title, level=0)

    for kind, content in _lines_struct(md):
        if kind in ("h1", "h2", "h3"):
            p = doc.add_heading("", level=int(kind[1]))
            _docx_add_inline(p, content)
        elif kind == "bullet":
            p = doc.add_paragraph(style="List Bullet")
            _docx_add_inline(p, content)
        elif kind == "numbered":
            p = doc.add_paragraph(style="List Number")
            _docx_add_inline(p, re.sub(r"^\s*\d+[.)]\s*", "", content))
        elif kind == "table":
            rows = _table_rows(content)
            if rows:
                t = doc.add_table(rows=len(rows), cols=len(rows[0]))
                try:
                    t.style = "Light Grid Accent 1"
                except KeyError:
                    pass
                for ri, row in enumerate(rows):
                    for ci, cell in enumerate(row):
                        tc = t.rows[ri].cells[ci]
                        tc.text = ""
                        _docx_add_inline(tc.paragraphs[0], cell)
                        if ri == 0:
                            for run in tc.paragraphs[0].runs:
                                run.bold = True
        elif kind in ("muted", "src"):
            p = doc.add_paragraph()
            _docx_add_inline(p, content)
            for run in p.runs:
                run.italic = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x6b, 0x72, 0x80)
        elif kind == "hr":
            doc.add_paragraph("─" * 50)
        elif kind == "p":
            p = doc.add_paragraph()
            _docx_add_inline(p, content)
        # blank -> atla
    try:
        from .imza import doc_meta
        m = doc_meta()
        doc.core_properties.author = m["author"]
        doc.core_properties.comments = m["creator"]
        doc.core_properties.last_modified_by = m["creator"]
    except Exception:
        pass
    doc.save(out_path)
    return out_path


# ============================= PDF =============================
def _rl_esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rl_inline(text):
    out = []
    for chunk, kind in _inline_tokens(text):
        chunk = _rl_esc(chunk)
        if kind == "bold":
            out.append(f"<b>{chunk}</b>")
        elif kind == "code":
            out.append(f'<font face="Courier">{chunk}</font>')
        else:
            out.append(chunk)
    return "".join(out) or " "


_FONTS_READY = False


def _register_turkish_fonts():
    """PDF'in temel 14 yazı tipi (Helvetica vb.) Türkçe'ye özgü ı/ş/ğ harflerini BASAMAZ (WinAnsi kodlaması
    bu harfleri içermez). reportlab'ın kendi paketiyle gelen Unicode TTF (Vera/Bitstream Vera Sans) bu
    harfleri doğru basar; her kurulumda hazır bulunduğu için ek bir font dosyası taşımaya gerek kalmaz."""
    global _FONTS_READY
    if _FONTS_READY:
        return
    import os
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    base = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    pdfmetrics.registerFont(TTFont("Vera", os.path.join(base, "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("VeraBd", os.path.join(base, "VeraBd.ttf")))
    pdfmetrics.registerFont(TTFont("VeraIt", os.path.join(base, "VeraIt.ttf")))
    pdfmetrics.registerFont(TTFont("VeraBI", os.path.join(base, "VeraBI.ttf")))
    pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="VeraBd", italic="VeraIt", boldItalic="VeraBI")
    _FONTS_READY = True


def _pdf_meta():
    try:
        from .imza import doc_meta
        m = doc_meta()
        return {"author": m["author"], "creator": m["creator"], "producer": m["producer"]}
    except Exception:
        return {}


def export_pdf(md, out_path, title=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

    _register_turkish_fonts()
    styles = getSampleStyleSheet()
    h_styles = {
        1: ParagraphStyle("h1x", parent=styles["Heading1"], fontName="VeraBd", fontSize=18,
                          spaceBefore=14, spaceAfter=9, textColor=colors.HexColor("#111827")),
        2: ParagraphStyle("h2x", parent=styles["Heading2"], fontName="VeraBd", fontSize=13.5,
                          spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#047857")),
        3: ParagraphStyle("h3x", parent=styles["Heading3"], fontName="VeraBd", fontSize=11.5,
                          spaceBefore=9, spaceAfter=4, textColor=colors.HexColor("#111827")),
    }
    body = ParagraphStyle("bodyx", parent=styles["Normal"], fontName="Vera", fontSize=10.3, leading=14.5,
                          spaceAfter=5)
    bullet_style = ParagraphStyle("bulletx", parent=body, leftIndent=14, bulletIndent=0)
    muted_style = ParagraphStyle("mutedx", parent=body, fontName="VeraIt", textColor=colors.HexColor("#6b7280"),
                                 fontSize=8.8)

    story = []
    if title:
        story.append(Paragraph(_rl_esc(title), h_styles[1]))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#d1d5db"), thickness=1))
        story.append(Spacer(1, 10))

    for kind, content in _lines_struct(md):
        if kind in ("h1", "h2", "h3"):
            story.append(Paragraph(_rl_inline(content), h_styles[int(kind[1])]))
        elif kind == "bullet":
            story.append(Paragraph("•  " + _rl_inline(content), bullet_style))
        elif kind == "numbered":
            story.append(Paragraph(_rl_inline(content), bullet_style))
        elif kind == "table":
            rows = _table_rows(content)
            if rows:
                data = [[Paragraph(_rl_inline(c), body) for c in row] for row in rows]
                t = Table(data, hAlign="LEFT")
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))
        elif kind in ("muted", "src"):
            story.append(Paragraph(_rl_inline(content), muted_style))
        elif kind == "hr":
            story.append(HRFlowable(width="100%", color=colors.HexColor("#e5e7eb"), thickness=0.7))
            story.append(Spacer(1, 6))
        elif kind == "p":
            story.append(Paragraph(_rl_inline(content), body))
        elif kind == "blank":
            story.append(Spacer(1, 4))

    doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm, title=title or "FENIX Rapor",
                            **_pdf_meta())
    doc.build(story)
    return out_path
