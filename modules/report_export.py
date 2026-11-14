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

# ------------------------------------------------------------------ v1.4: yapı taşları ve tema
# Sabit şablon yok: model içeriğe göre hangi yapı taşlarını, hangi sırayla kullanacağına kendisi karar verir;
# kod her yapı taşını aynı kalitede çizer. Böylece her belge farklı görünür ama hepsi düzenli olur.
#   ::: tanim Fotosentez          (kutunun başlığı isteğe bağlı)
#   Bitkilerin ışık enerjisini ...
#   :::
BLOKLAR = {
    "tanim": ("Tanım", "#2563eb"), "ornek": ("Örnek", "#059669"), "ipucu": ("İpucu", "#d97706"),
    "uyari": ("Dikkat", "#dc2626"), "ozet": ("Özet", None), "formul": ("Formül", "#475569"),
    "soru": ("Soru – Cevap", None), "not": ("Not", "#64748b"), "alinti": ("Alıntı", "#7c3aed"),
    "adim": ("Adım adım", None), "tahmin": ("Doğrulanmamış bilgi", "#b45309"),
}
_BLOK_ESANLAM = {"tanım": "tanim", "örnek": "ornek", "uyarı": "uyari", "dikkat": "uyari", "özet": "ozet",
                 "formül": "formul", "soru-cevap": "soru", "sorular": "soru", "adımlar": "adim", "adım": "adim"}
TEMALAR = {"mavi": "#1d4ed8", "yesil": "#047857", "mor": "#6d28d9", "turuncu": "#c2410c", "kirmizi": "#b91c1c",
           "lacivert": "#1e3a8a", "turkuaz": "#0f766e", "gri": "#334155", "pembe": "#be185d"}
_TEMA_ESANLAM = {"yeşil": "yesil", "kırmızı": "kirmizi", "turkuvaz": "turkuaz"}
_TEMA_RE = re.compile(r"<!--\s*tema\s*:\s*([a-zçğıöşü]+)\s*-->", re.IGNORECASE)


def tema_rengi(md):
    """Belgedeki '<!-- tema: yesil -->' satırından ana renk; yoksa mavi."""
    m = _TEMA_RE.search(md or "")
    ad = (m.group(1).lower() if m else "mavi")
    return TEMALAR.get(_TEMA_ESANLAM.get(ad, ad), TEMALAR["mavi"])


def _blok_turu(ad):
    ad = (ad or "").strip().lower()
    ad = _BLOK_ESANLAM.get(ad, ad)
    return ad if ad in BLOKLAR else "not"


def _acik_ton(hex_renk, oran=0.9):
    """Rengi beyaza doğru açar (kutu arka planı için)."""
    h = hex_renk.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (round(c + (255 - c) * oran) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


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


def _gizli_yorum(satir):
    """Satırın tamamı tek bir <!-- ... --> yorumu mu (imza satırı)? Regex yerine düz kontrol (CodeQL #4/#5)."""
    st = (satir or "").strip()
    return st.startswith("<!--") and st.endswith("-->") and "-->" not in st[4:-3]


def _lines_struct(md):
    """Markdown'ı (tür, içerik) listesine çevirir. Tür: h1/h2/h3, bullet, numbered, table, muted, src,
    hr, p, blank. app.py'deki render_markdown ile aynı ayrıştırma kurallarını izler."""
    lines = (md or "").splitlines()
    lines = [x for x in lines if not _gizli_yorum(x)]   # gizli yorumlar (imza) gösterilmez
    out, i, in_sources = [], 0, False
    while i < len(lines):
        line = lines[i]
        st = line.strip()
        m_blok = re.match(r"^:{3,}\s*([A-Za-zÇĞİÖŞÜçğıöşü\-]+)\s*(.*)$", st)
        if m_blok:
            tur, baslik, icerik = _blok_turu(m_blok.group(1)), m_blok.group(2).strip(), []
            i += 1
            while i < len(lines) and not re.fullmatch(r":{3,}", lines[i].strip()):
                icerik.append(lines[i])
                i += 1
            i += 1                                       # kapanış ':::'
            out.append(("blok", (tur, baslik, icerik)))
            continue
        if st.startswith(">"):
            out.append(("quote", st.lstrip("> ").strip()))
            i += 1
            continue
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
def _docx_add_inline(paragraph, text, renk=None):
    for chunk, kind in _inline_tokens(text):
        if not chunk:
            continue
        run = paragraph.add_run(chunk)
        if kind == "bold":
            run.bold = True
        elif kind == "code":
            run.font.name = "Consolas"
        if renk is not None:
            run.font.color.rgb = renk


def _rgb(hex_renk):
    from docx.shared import RGBColor
    return RGBColor.from_string(hex_renk.lstrip("#").upper())


def _docx_golge(hucre, hex_renk):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_renk.lstrip("#"))
    hucre._tc.get_or_add_tcPr().append(shd)


def _docx_sayfa_no(doc):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    p = doc.sections[0].footer.paragraphs[0]
    p.text = "FENIX · sayfa "
    run = p.add_run()
    for tur, metin in (("begin", None), (None, "PAGE"), ("end", None)):
        if tur:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), tur)
        else:
            e = OxmlElement("w:instrText")
            e.text = metin
        run._r.append(e)


def _docx_blok(doc, tur, baslik, icerik, tema):
    from docx.shared import Pt
    ad, renk = BLOKLAR[tur]
    renk = renk or tema
    t = doc.add_table(rows=1, cols=1)
    c = t.rows[0].cells[0]
    _docx_golge(c, _acik_ton(renk, 0.88))
    p = c.paragraphs[0]
    r = p.add_run(f"{ad}" + (f": {baslik}" if baslik else ""))
    r.bold = True
    r.font.color.rgb = _rgb(renk)
    sira = 0
    p.paragraph_format.space_after = Pt(2)
    for satir in icerik:
        st = satir.strip()
        if not st:
            continue
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        if tur == "formul":
            r = p.add_run(st)
            r.font.name = "Consolas"
            r.font.size = Pt(11)
            continue
        if tur == "soru" and re.match(r"^[SC][:.)]\s*", st):
            _docx_add_inline(p, ("**" + st + "**") if st[0] == "S" else st)
            continue
        if re.match(r"^[-*+]\s+", st):
            st = "• " + re.sub(r"^[-*+]\s+", "", st)
        elif tur == "adim":
            sira += 1
            st = f"{sira}. " + re.sub(r"^\d+[.)]\s*", "", st)
        _docx_add_inline(p, st)
    doc.add_paragraph()


def export_docx(md, out_path, title=None):
    from docx import Document
    from docx.shared import Pt, RGBColor

    tema = tema_rengi(md)
    doc = Document()
    yapi = _lines_struct(md)
    if not title and yapi and yapi[0][0] == "h1":       # ilk # başlık belgenin başlığıdır
        title, yapi = yapi[0][1], yapi[1:]
    if title:
        h = doc.add_heading("", level=0)
        _docx_add_inline(h, title, _rgb(tema))

    for kind, content in yapi:
        if kind in ("h1", "h2", "h3"):
            p = doc.add_heading("", level=int(kind[1]))
            _docx_add_inline(p, content, _rgb(tema) if kind != "h3" else None)
        elif kind == "blok":
            _docx_blok(doc, *content, tema)
        elif kind == "quote":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            _docx_add_inline(p, content)
            for run in p.runs:
                run.italic = True
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
                    t.style = "Table Grid"
                except KeyError:
                    pass
                for ri, row in enumerate(rows):
                    for ci, cell in enumerate(row):
                        tc = t.rows[ri].cells[ci]
                        tc.text = ""
                        _docx_add_inline(tc.paragraphs[0], cell, RGBColor(0xFF, 0xFF, 0xFF) if ri == 0 else None)
                        if ri == 0:
                            _docx_golge(tc, tema)
                            for run in tc.paragraphs[0].runs:
                                run.bold = True
                doc.add_paragraph()
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
        _docx_sayfa_no(doc)
    except Exception:
        pass
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
            out.append(f'<font face="{MONO}">{chunk}</font>')
        else:
            out.append(chunk)
    return "".join(out) or " "


_FONTS_READY = False
MONO = "Courier"


def _register_turkish_fonts():
    """PDF'in temel yazı tipleri (Helvetica, Courier) ı/ş/ğ harflerini, alt simgeleri (CO₂) ve okları (→) basamaz.
    Önce Windows'un Segoe UI / Consolas yazı tipleri, yoksa DejaVu (Linux), en son reportlab'la gelen Vera kullanılır.
    Aile adı her durumda 'Vera' kalır ki stil tanımları değişmesin; eşaralıklı yazı tipi MONO'dadır."""
    global _FONTS_READY, MONO
    if _FONTS_READY:
        return
    import os
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    dv = "/usr/share/fonts/truetype/dejavu"
    vera = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    adaylar = [
        [os.path.join(win, f) for f in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf")],
        [os.path.join(dv, f) for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf",
                                       "DejaVuSans-BoldOblique.ttf")],
        [os.path.join(vera, f) for f in ("Vera.ttf", "VeraBd.ttf", "VeraIt.ttf", "VeraBI.ttf")],
    ]
    for dosyalar in adaylar:
        if all(os.path.exists(f) for f in dosyalar):
            for ad, f in zip(("Vera", "VeraBd", "VeraIt", "VeraBI"), dosyalar):
                pdfmetrics.registerFont(TTFont(ad, f))
            break
    pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="VeraBd", italic="VeraIt", boldItalic="VeraBI")
    for f in (os.path.join(win, "consola.ttf"), os.path.join(dv, "DejaVuSansMono.ttf")):
        if os.path.exists(f):
            pdfmetrics.registerFont(TTFont("FMono", f))
            MONO = "FMono"
            break
    _FONTS_READY = True


def _pdf_meta():
    try:
        from .imza import doc_meta
        m = doc_meta()
        return {"author": m["author"], "creator": m["creator"], "producer": m["producer"]}
    except Exception:
        return {}


def export_pdf(md, out_path, title=None):
    import datetime
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether

    _register_turkish_fonts()
    tema = tema_rengi(md)
    T = colors.HexColor(tema)
    styles = getSampleStyleSheet()
    h_styles = {
        1: ParagraphStyle("h1x", parent=styles["Heading1"], fontName="VeraBd", fontSize=17,
                          spaceBefore=16, spaceAfter=8, textColor=T),
        2: ParagraphStyle("h2x", parent=styles["Heading2"], fontName="VeraBd", fontSize=13.5,
                          spaceBefore=14, spaceAfter=4, textColor=T),
        3: ParagraphStyle("h3x", parent=styles["Heading3"], fontName="VeraBd", fontSize=11.5,
                          spaceBefore=9, spaceAfter=4, textColor=colors.HexColor("#111827")),
    }
    body = ParagraphStyle("bodyx", parent=styles["Normal"], fontName="Vera", fontSize=10.3, leading=14.8,
                          spaceAfter=5)
    bullet_style = ParagraphStyle("bulletx", parent=body, leftIndent=14, bulletIndent=0)
    muted_style = ParagraphStyle("mutedx", parent=body, fontName="VeraIt", textColor=colors.HexColor("#6b7280"),
                                 fontSize=8.8)
    quote_style = ParagraphStyle("quotex", parent=body, fontName="VeraIt", leftIndent=12,
                                 textColor=colors.HexColor("#374151"))
    kapak_bas = ParagraphStyle("kapak", parent=body, fontName="VeraBd", fontSize=21, leading=26,
                               textColor=colors.white)
    kapak_alt = ParagraphStyle("kapakalt", parent=body, fontSize=9.5, textColor=colors.HexColor("#e5e7eb"))
    kutu_bas = ParagraphStyle("kutubas", parent=body, fontName="VeraBd", fontSize=10.5, spaceAfter=3)
    formul_style = ParagraphStyle("formul", parent=body, fontName=MONO, fontSize=11, alignment=1)

    yapi = _lines_struct(md)
    if not title and yapi and yapi[0][0] == "h1":        # ilk # başlık kapak olur
        title, yapi = yapi[0][1], yapi[1:]

    story = []
    if title:
        aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
                 "Kasım", "Aralık"]
        b = datetime.date.today()
        kapak = Table([[Paragraph(_rl_inline(title), kapak_bas)],
                       [Paragraph(f"{b.day} {aylar[b.month - 1]} {b.year} · FENIX", kapak_alt)]],
                      colWidths=["100%"])
        kapak.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), T),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                                   ("TOPPADDING", (0, 0), (-1, 0), 16), ("BOTTOMPADDING", (0, -1), (-1, -1), 12)]))
        story += [kapak, Spacer(1, 12)]
    basliklar = [c for k, c in yapi if k in ("h1", "h2")]
    if len(basliklar) >= 5:                              # uzun belgede içindekiler
        story.append(Paragraph("İçindekiler", h_styles[3]))
        for n, b_ in enumerate(basliklar, 1):
            story.append(Paragraph(f"{n}. {_rl_inline(b_)}", bullet_style))
        story.append(Spacer(1, 8))

    def kutu(tur, baslik, icerik):
        ad, renk = BLOKLAR[tur]
        R = colors.HexColor(renk or tema)
        satirlar = [Paragraph(f'<font color="{renk or tema}">{_rl_esc(ad)}</font>'
                              + (f": {_rl_inline(baslik)}" if baslik else ""), kutu_bas)]
        sira = 0
        for sat in icerik:
            st = sat.strip()
            if not st:
                continue
            if tur == "formul":
                satirlar.append(Paragraph(_rl_esc(st), formul_style))
                continue
            if tur == "soru" and re.match(r"^[SC][:.)]\s*", st):
                satirlar.append(Paragraph(("<b>%s</b>" if st[0] == "S" else "%s") % _rl_inline(st), body))
                continue
            if re.match(r"^[-*+]\s+", st):
                st = "•  " + re.sub(r"^[-*+]\s+", "", st)
            elif tur == "adim":
                sira += 1
                st = f"<b>{sira}.</b> " + _rl_inline(re.sub(r"^\d+[.)]\s*", "", st))
                satirlar.append(Paragraph(st, body))
                continue
            satirlar.append(Paragraph(_rl_inline(st), body))
        t = Table([[s_] for s_ in satirlar], colWidths=["100%"])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_acik_ton(renk or tema, 0.9))),
                               ("LINEBEFORE", (0, 0), (0, -1), 3, R),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                               ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
                               ("TOPPADDING", (0, 1), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -2), 1)]))
        return KeepTogether([t, Spacer(1, 8)]) if len(satirlar) <= 12 else t

    for kind, content in yapi:
        if kind in ("h1", "h2"):
            story.append(Paragraph(_rl_inline(content), h_styles[2 if kind == "h2" else 1]))
            story.append(HRFlowable(width="100%", color=colors.HexColor(_acik_ton(tema, 0.6)), thickness=0.8,
                                    spaceAfter=4))
        elif kind == "h3":
            story.append(Paragraph(_rl_inline(content), h_styles[3]))
        elif kind == "blok":
            story.append(kutu(*content))
        elif kind == "quote":
            story.append(Paragraph(_rl_inline(content), quote_style))
        elif kind == "bullet":
            story.append(Paragraph("•  " + _rl_inline(content), bullet_style))
        elif kind == "numbered":
            story.append(Paragraph(_rl_inline(content), bullet_style))
        elif kind == "table":
            rows = _table_rows(content)
            if rows:
                data = [[Paragraph(f'<font color="white"><b>{_rl_inline(c)}</b></font>', body) for c in rows[0]]]
                data += [[Paragraph(_rl_inline(c), body) for c in row] for row in rows[1:]]
                t = Table(data, hAlign="LEFT", repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), T),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(_acik_ton(tema, 0.94))]),
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

    def sayfa(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Vera", 8)
        canvas.setFillColor(colors.HexColor("#9ca3af"))
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"FENIX · sayfa {doc_.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm, title=title or "FENIX Belge",
                            **_pdf_meta())
    doc.build(story, onFirstPage=sayfa, onLaterPages=sayfa)
    return out_path
