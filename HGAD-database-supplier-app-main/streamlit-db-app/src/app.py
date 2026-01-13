import os
import re
import base64
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Dict, List

import pandas as pd
import streamlit as st

# ReportLab (PDF) + Arabic shaping
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    Image as RLImage, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

try:
    from PIL import Image as PILImage
except Exception:
    PILImage = None

# Local imports
from db.connection import (
    get_db_connection,
    fetch_companies,
    fetch_financial_report,
    fetch_invoices_data
)
from components.filters import (
    create_company_dropdown,
    create_project_dropdown,
    create_type_dropdown,
    create_date_range,
    create_column_search,
    create_raw_material_dropdown,
    create_supplier_multiselect
)
from utils.data_helpers import (
    format_numbers_for_display,
    apply_date_filter,
    apply_column_search,
    safe_filename,
    compose_export_title,
    format_value
)

# =========================================================
# Paths & Assets
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

LOGO_CANDIDATES = [ASSETS_DIR / "logo.png"]
WIDE_LOGO_CANDIDATES = [
    ASSETS_DIR / "logo_wide.png",
    ASSETS_DIR / "logo_wide.jpg",
    ASSETS_DIR / "logo_wide.jpeg",
]

AR_FONT_CANDIDATES = [
    ASSETS_DIR / "Cairo-Regular.ttf",
    ASSETS_DIR / "Amiri-Regular.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

_AR_RE = re.compile(r"[\u0600-\u06FF]")

# =========================================================
# Utility Functions
# =========================================================

def _first_existing(paths) -> Optional[Path]:
    """إيجاد أول ملف موجود من قائمة المسارات"""
    for p in paths:
        pth = Path(p)
        if pth.exists() and pth.is_file() and pth.stat().st_size > 0:
            return pth
    return None


def _image_size(path: Path) -> Tuple[int, int]:
    """الحصول على أبعاد الصورة"""
    if PILImage:
        try:
            with PILImage.open(path) as im:
                return im.size
        except Exception:
            pass
    return (600, 120)


def _site_logo_path() -> Optional[Path]:
    """مسار الشعار الصغير"""
    return _first_existing(LOGO_CANDIDATES)


def _wide_logo_path() -> Optional[Path]:
    """مسار الشعار العريض"""
    return _first_existing(WIDE_LOGO_CANDIDATES)


def _first_existing_font_path() -> Optional[str]:
    """مسار الخط العربي"""
    p = _first_existing(AR_FONT_CANDIDATES)
    return str(p) if p else None


def register_arabic_font() -> Tuple[str, bool]:
    """تسجيل الخط العربي لـ ReportLab"""
    p = _first_existing_font_path()
    if p:
        name = os.path.splitext(os.path.basename(p))[0]
        try:
            pdfmetrics.registerFont(TTFont(name, p))
            return name, True
        except Exception:
            pass
    return "Helvetica", False


def looks_arabic(s: str) -> bool:
    """التحقق من وجود نص عربي"""
    return bool(_AR_RE.search(str(s or "")))


def shape_arabic(s: str) -> str:
    """تشكيل النص العربي للعرض الصحيح في PDF"""
    try:
        return get_display(arabic_reshaper.reshape(str(s)))
    except Exception:
        return str(s)


# =========================================================
# Streamlit Page Config & CSS
# =========================================================

st.set_page_config(
    page_title="قاعدة بيانات الموردين | HGAD",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root {
  --bg: #0a0f1a;
  --panel: #0f172a;
  --panel-2: #0b1220;
  --muted: #9fb2d9;
  --text: #e5e7eb;
  --accent: #1E3A8A;
  --accent-2: #2563eb;
  --line: #23324d;
}

html, body {
  direction: rtl !important;
  text-align: right !important;
  font-family: "Cairo", "Noto Kufi Arabic", "Segoe UI", Tahoma, sans-serif !important;
  color: var(--text) !important;
  background: var(--bg) !important;
}

[data-testid="stSidebar"] {
  transform: none !important;
  visibility: visible !important;
  width: 340px !important;
  min-width: 340px !important;
  background: linear-gradient(180deg, #0b1220, #0a1020);
  border-inline-start: 1px solid var(--line);
}

[data-testid="collapsedControl"],
button[kind="header"],
button[title="Expand sidebar"],
button[title="Collapse sidebar"],
[data-testid="stSidebarCollapseButton"] {
  display: none !important;
}

.hr-accent {
  height: 2px;
  border: 0;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  margin: 8px 0 14px;
}

.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 14px;
  box-shadow: 0 6px 24px rgba(3,10,30,.25);
}

.card.soft {
  background: var(--panel-2);
}

.date-box {
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 12px;
  background: var(--panel-2);
  margin-bottom: 12px;
}

.date-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

[data-testid="stDateInput"] input {
  background: #0f172a !important;
  color: var(--text) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  text-align: center !important;
  height: 44px !important;
  min-width: 190px !important;
}

[data-testid="stDateInput"] label {
  color: var(--muted) !important;
  font-weight: 700;
}

.hsec {
  color: #e7eefc;
  font-weight: 900;
  margin: 6px 0 10px;
  font-size: 22px;
}

/* Improved Streamlit dataframe styling */
[data-testid="stDataFrame"] {
  width: 100% !important;
}

[data-testid="stDataFrame"] > div {
  width: 100% !important;
}

[data-testid="stDataFrame"] table {
  width: 100% !important;
  table-layout: auto !important;
}

[data-testid="stDataFrame"] thead tr th {
  position: sticky !important;
  top: 0 !important;
  z-index: 2 !important;
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%) !important;
  color: #ffffff !important;
  font-weight: 800 !important;
  text-align: center !important;
  border: 1px solid rgba(255,255,255,0.1) !important;
  font-size: 14px !important;
  padding: 12px 8px !important;
  white-space: nowrap !important;
}

[data-testid="stDataFrame"] tbody tr {
  transition: background 0.2s ease !important;
}

[data-testid="stDataFrame"] tbody tr:nth-child(even) {
  background: rgba(255,255,255,0.02) !important;
}

[data-testid="stDataFrame"] tbody tr:hover {
  background: #1a2744 !important;
}

[data-testid="stDataFrame"] tbody td {
  padding: 10px 8px !important;
  border: 1px solid var(--line) !important;
  text-align: center !important;
  color: var(--text) !important;
  font-size: 13px !important;
  white-space: nowrap !important;
}

/* Link styling in dataframe */
[data-testid="stDataFrame"] a {
  color: #60a5fa !important;
  text-decoration: none !important;
  font-weight: 600 !important;
  transition: all 0.2s ease !important;
}

[data-testid="stDataFrame"] a:hover {
  color: #93c5fd !important;
  text-decoration: underline !important;
}

.hsec, h1, h3 {
  text-align: right !important;
  direction: rtl !important;
}

/* Download buttons styling */
[data-testid="stDownloadButton"] button {
  width: 100% !important;
  border-radius: 8px !important;
  font-weight: 700 !important;
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%) !important;
  border: none !important;
  color: white !important;
  padding: 12px 20px !important;
  transition: all 0.2s ease !important;
}

[data-testid="stDownloadButton"] button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4) !important;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# Header with Logo
# =========================================================

def _logo_html() -> str:
    """HTML للشعار كـ Base64"""
    p = _site_logo_path()
    if not p:
        return ""
    ext = p.suffix.lower().lstrip(".") or "png"
    mime = f"image/{'jpeg' if ext in ('jpg','jpeg') else ext}"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f'<img src="data:{mime};base64,{b64}" width="64" />'


c_logo, c_title = st.columns([1, 6], gap="small")
with c_logo:
    st.markdown(_logo_html(), unsafe_allow_html=True)
with c_title:
    st.markdown("""
<h1 style="color:#e7eefc; font-weight:900; margin:0;">
  قاعدة بيانات الموردين والتقارير المالية
  <span style="font-size:18px; color:#9fb2d9; font-weight:600;">| HGAD Company</span>
</h1>
""", unsafe_allow_html=True)

st.markdown('<hr class="hr-accent"/>', unsafe_allow_html=True)

# =========================================================
# Excel Export Functions (ENHANCED)
# =========================================================

def _pick_excel_engine() -> Optional[str]:
    """اختيار محرك Excel المتاح"""
    try:
        import xlsxwriter
        return "xlsxwriter"
    except Exception:
        pass
    try:
        import openpyxl
        return "openpyxl"
    except Exception:
        return None


def _estimate_col_widths_chars(df: pd.DataFrame) -> List[float]:
    """تقدير عرض الأعمدة بالأحرف"""
    widths = []
    for col in df.columns:
        series = df[col]
        max_len = max([len(str(col))] + [len(str(v)) for v in series.values])
        widths.append(min(max_len + 4, 60))
    return widths


def _chars_to_pixels(chars: float) -> float:
    """تحويل الأحرف إلى بكسلات (≈7.2 px per char)"""
    return chars * 7.2


def _insert_wide_logo(ws, df: pd.DataFrame, start_row: int, start_col: int = 0) -> int:
    """
    إدراج الشعار العريض ليغطي عرض الجدول كاملاً
    يُرجع رقم الصف التالي للعنوان
    """
    wlp = _wide_logo_path()
    if not wlp:
        return start_row

    widths_chars = _estimate_col_widths_chars(df)
    total_width_px = _chars_to_pixels(sum(widths_chars))

    try:
        img_w_px, img_h_px = _image_size(wlp)
        if img_w_px <= 0:
            img_w_px = 1000
        x_scale = max(0.1, total_width_px / float(img_w_px))
        y_scale = x_scale  # keep aspect ratio
        ws.insert_image(
            start_row, start_col, str(wlp),
            {"x_scale": x_scale, "y_scale": y_scale, "object_position": 2}
        )
        scaled_h_px = img_h_px * y_scale
        ws.set_row(start_row, int(scaled_h_px * 0.75))  # px→pt approx
        return start_row + 1
    except Exception:
        ws.set_row(start_row, 80)
        ws.insert_image(start_row, start_col, str(wlp), {"x_scale": 0.5, "y_scale": 0.5, "object_position": 2})
        return start_row + 1


def _write_excel_table(ws, workbook, df: pd.DataFrame, start_row: int, start_col: int) -> Tuple[int, int, int, int]:
    """كتابة DataFrame كجدول Excel منسق مع روابط قابلة للنقر"""
    hdr_fmt = workbook.add_format({"align": "right", "bold": True, "bg_color": "#1E3A8A", "font_color": "white"})
    fmt_text = workbook.add_format({"align": "right"})
    fmt_date = workbook.add_format({"align": "right", "num_format": "yyyy-mm-dd"})
    fmt_num = workbook.add_format({"align": "right", "num_format": "#,##0.00"})
    fmt_link = workbook.add_format({"font_color": "blue", "underline": 1, "align": "right"})

    r0, c0 = start_row, start_col

    # Headers
    for j, col in enumerate(df.columns):
        ws.write(r0, c0 + j, col, hdr_fmt)

    # Body
    for i in range(len(df)):
        for j, col in enumerate(df.columns):
            val = df.iloc[i, j]
            colname = str(col)
            sval = "" if pd.isna(val) else str(val)
            
            # Check if this is a URL column
            if sval.startswith(("http://", "https://")) or ("رابط" in colname and sval):
                ws.write_url(r0 + 1 + i, c0 + j, sval, fmt_link, string="فتح الرابط")
            else:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    if pd.notna(val):
                        ws.write_datetime(r0 + 1 + i, c0 + j, pd.to_datetime(val), fmt_date)
                    else:
                        ws.write_blank(r0 + 1 + i, c0 + j, None, fmt_text)
                elif pd.api.types.is_numeric_dtype(df[col]):
                    if pd.notna(val):
                        ws.write_number(r0 + 1 + i, c0 + j, float(val), fmt_num)
                    else:
                        ws.write_blank(r0 + 1 + i, c0 + j, None, fmt_text)
                else:
                    ws.write(r0 + 1 + i, c0 + j, sval, fmt_text)

    # Add sum row for numeric columns
    sum_row_idx = r0 + 1 + len(df)
    exclude_keywords = ['id', 'رقم', 'تاريخ', 'date', 'code', 'كود', 'بنك', 'bank', 'نوع', 'type', 'رابط', 'مورد', 'مواد']
    
    if len(df.columns) > 0:
        ws.write(sum_row_idx, c0, "المجموع", hdr_fmt)
    
    for j, col in enumerate(df.columns):
        if j == 0:
            continue
            
        col_lower = str(col).lower()
        should_exclude = any(keyword in col_lower for keyword in exclude_keywords)
        
        if not should_exclude:
            try:
                numeric_col = pd.to_numeric(df[col], errors='coerce')
                if not numeric_col.isna().all():
                    s = numeric_col.sum()
                    if not pd.isna(s) and abs(s) > 0.001:
                        ws.write(sum_row_idx, c0 + j, s, fmt_num)
                    else:
                        ws.write(sum_row_idx, c0 + j, "", fmt_text)
                else:
                    ws.write(sum_row_idx, c0 + j, "", fmt_text)
            except Exception:
                ws.write(sum_row_idx, c0 + j, "", fmt_text)
        else:
            ws.write(sum_row_idx, c0 + j, "", fmt_text)

    # Add count row
    count_row_idx = sum_row_idx + 1
    if len(df.columns) > 0:
        ws.write(count_row_idx, c0, "عدد الصفوف", hdr_fmt)
    
    if len(df.columns) > 1:
        total_rows = len(df)
        ws.write(count_row_idx, c0 + 1, total_rows, fmt_text)
        for j in range(len(df.columns)):
            if j == 0 or j == 1:
                continue
            ws.write(count_row_idx, c0 + j, "", fmt_text)

    r1 = count_row_idx
    c1 = c0 + len(df.columns) - 1

    # Add Excel table
    ws.add_table(r0, c0, r1, c1, {
        "style": "Table Style Medium 9",
        "columns": [{"header": str(c)} for c in df.columns]
    })
    ws.freeze_panes(r0 + 1, c0)

    # Set column widths
    widths_chars = _estimate_col_widths_chars(df)
    for j, w in enumerate(widths_chars):
        ws.set_column(c0 + j, c0 + j, w)

    return r0, c0, r1, c1


def make_excel_bytes(
    df: pd.DataFrame,
    sheet_name: str,
    title_line: str,
    put_logo: bool = True
) -> Optional[bytes]:
    """إنشاء ملف Excel مع تنسيق احترافي وروابط قابلة للنقر"""
    engine = _pick_excel_engine()
    if engine is None:
        return None
    
    buf = BytesIO()
    
    if engine == "xlsxwriter":
        with pd.ExcelWriter(buf, engine=engine) as writer:
            wb = writer.book
            safe_name = (sheet_name or "Sheet1")[:31]
            ws = wb.add_worksheet(safe_name)
            writer.sheets[safe_name] = ws

            cur_row = 0
            
            # Logo
            if put_logo:
                cur_row = _insert_wide_logo(ws, df, start_row=cur_row, start_col=0)

            # Title
            ncols = max(1, len(df.columns))
            title_fmt = wb.add_format({
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "font_size": 16,
                "bg_color": "#f0f0f0"
            })
            ws.merge_range(cur_row, 0, cur_row, ncols - 1, title_line, title_fmt)
            ws.set_row(cur_row, 28)
            cur_row += 1

            # One blank row
            ws.set_row(cur_row, 16)
            cur_row += 1

            # Table
            _write_excel_table(ws, wb, df, start_row=cur_row, start_col=0)
            ws.set_zoom(115)
            ws.set_margins(left=0.3, right=0.3, top=0.5, bottom=0.5)
    else:
        # Fallback for openpyxl
        with pd.ExcelWriter(buf, engine=engine) as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    
    buf.seek(0)
    return buf.getvalue()


def make_csv_utf8(df: pd.DataFrame) -> bytes:
    """إنشاء ملف CSV بترميز UTF-8"""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


# =========================================================
# PDF Export Functions (ENHANCED)
# =========================================================

def _pdf_header_elements(title_line: str) -> Tuple[List, float]:
    """إنشاء عناصر رأس PDF مع الشعار"""
    font_name, arabic_ok = register_arabic_font()
    page = landscape(A4)
    left, right, top, bottom = 14, 14, 18, 14
    avail_w = page[0] - left - right
    
    title_style = ParagraphStyle(
        name="Title",
        fontName=font_name,
        fontSize=14,
        leading=17,
        alignment=1,
        textColor=colors.HexColor("#1b1b1b")
    )
    
    if arabic_ok:
        title_line = shape_arabic(title_line)
    
    elements = []
    
    # Add wide logo if exists
    wlp = _wide_logo_path()
    if wlp and wlp.exists():
        try:
            if PILImage:
                w_px, h_px = _image_size(wlp)
                ratio = h_px / float(w_px) if w_px else 0.2
                img_h = max(22, avail_w * ratio * 0.55)
            else:
                img_h = 36
            
            logo_img = RLImage(str(wlp), hAlign="CENTER")
            logo_img.drawWidth = avail_w
            logo_img.drawHeight = img_h
            elements.append(logo_img)
            elements.append(Spacer(1, 8))
        except Exception:
            pass
    
    elements.append(Paragraph(title_line, title_style))
    elements.append(Spacer(1, 8))
    
    return elements, avail_w


def _pdf_table(
    df: pd.DataFrame,
    title: str = "",
    max_col_width: int = 120,
    font_size: float = 8.0,
    avail_width: Optional[float] = None
) -> list:
    """إنشاء جدول PDF منسق مع روابط قابلة للنقر"""
    font_name, _ = register_arabic_font()
    
    hdr_style = ParagraphStyle(
        name="Hdr",
        fontName=font_name,
        fontSize=font_size + 0.6,
        textColor=colors.whitesmoke,
        alignment=1,
        leading=font_size + 1.8
    )
    
    cell_rtl = ParagraphStyle(
        name="CellR",
        fontName=font_name,
        fontSize=font_size,
        leading=font_size + 1.5,
        alignment=2,
        textColor=colors.black
    )
    
    cell_ltr = ParagraphStyle(
        name="CellL",
        fontName=font_name,
        fontSize=font_size,
        leading=font_size + 1.5,
        alignment=0,
        textColor=colors.black
    )
    
    link_style = ParagraphStyle(
        name="Link",
        fontName=font_name,
        fontSize=font_size,
        alignment=2,
        textColor=colors.HexColor("#1a56db"),
        underline=True
    )
    
    blocks = []
    
    if title:
        tstyle = ParagraphStyle(
            name="Sec",
            fontName=font_name,
            fontSize=font_size + 2,
            alignment=2,
            textColor=colors.HexColor("#1E3A8A")
        )
        blocks += [Paragraph(shape_arabic(title), tstyle), Spacer(1, 4)]
    
    # Create header row
    headers = [
        Paragraph(
            shape_arabic(c) if looks_arabic(c) else str(c),
            hdr_style
        )
        for c in df.columns
    ]
    
    rows = [headers]
    
    # Create data rows
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            sval = "" if pd.isna(r[c]) else str(r[c])
            
            # Check if this is a URL column and has a valid URL
            if sval.startswith(("http://", "https://")) or ("رابط" in str(c) and sval):
                # Create clickable link in PDF
                link_html = f'<link href="{sval}">{shape_arabic("فتح الرابط")}</link>'
                cells.append(Paragraph(link_html, link_style))
            else:
                # Regular cell
                is_ar = looks_arabic(sval)
                cells.append(
                    Paragraph(
                        shape_arabic(sval) if is_ar else sval,
                        cell_rtl if is_ar else cell_ltr
                    )
                )
        rows.append(cells)
    
    # Calculate column widths
    col_widths = []
    for c in df.columns:
        max_len = max(len(str(c)), df[c].astype(str).map(len).max())
        col_widths.append(min(max_len * 6.4, max_col_width))
    
    if avail_width:
        total = sum(col_widths)
        if total > avail_width:
            factor = avail_width / total
            col_widths = [w * factor for w in col_widths]
    
    table = Table(rows, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#f7fafc")
        ]),
    ]))
    
    blocks.append(table)
    return blocks


def make_pdf_bytes(df: pd.DataFrame, title_line: str) -> bytes:
    """إنشاء ملف PDF احترافي مع شعار وتنسيق"""
    page = landscape(A4)
    left, right, top, bottom = 14, 14, 18, 14
    buf = BytesIO()
    
    doc = SimpleDocTemplate(
        buf,
        pagesize=page,
        rightMargin=right,
        leftMargin=left,
        topMargin=top,
        bottomMargin=bottom
    )
    
    elements, avail_w = _pdf_header_elements(title_line)
    
    # Choose font size based on number of columns
    n_cols = len(df.columns)
    if n_cols >= 12:
        max_col_width, base_font = 110, 7.0
    elif n_cols >= 9:
        max_col_width, base_font = 125, 7.5
    else:
        max_col_width, base_font = 150, 8.0
    
    elements += _pdf_table(
        df,
        max_col_width=max_col_width,
        font_size=base_font,
        avail_width=avail_w
    )
    
    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


# =========================================================
# Main Application
# =========================================================

def main():
    conn = get_db_connection()
    if conn is None:
        st.error("❌ فشل الاتصال بقاعدة البيانات. يرجى مراجعة الإعدادات.")
        return
    
    # Sidebar Filters
    with st.sidebar:
        st.title("🔍 عوامل التصفية")
        
        company_name = create_company_dropdown(conn)
        project_name = create_project_dropdown(conn, company_name)
        raw_material = create_raw_material_dropdown(conn)
        type_label, type_key = create_type_dropdown()
    
    if not company_name or not project_name or not type_key:
        st.info("📌 برجاء اختيار الشركة والمشروع ونوع البيانات من القائمة الجانبية.")
        return
    
    # Main Area Filters
    st.markdown('<div class="date-box">', unsafe_allow_html=True)
    
    # Date Filters
    st.markdown('<div class="date-row">', unsafe_allow_html=True)
    date_from, date_to = create_date_range()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Supplier Filter
    st.markdown("---")
    selected_suppliers = create_supplier_multiselect(conn, company_name, project_name, raw_material)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Fetch Data based on type
    if type_key == "financial_report":
        df = fetch_financial_report(
            conn,
            company_name,
            project_name,
            date_from,
            date_to,
            raw_material if raw_material != "الكل" else None,
            selected_suppliers if len(selected_suppliers) > 0 else None
        )
        display_name = "التقرير المالي"
    else:  # invoices
        df = fetch_invoices_data(
            conn,
            company_name,
            project_name,
            date_from,
            date_to,
            raw_material if raw_material != "الكل" else None,
            selected_suppliers if len(selected_suppliers) > 0 else None
        )
        display_name = "الفواتير"
    
    if df.empty:
        st.warning("⚠️ لا توجد بيانات مطابقة للاختيارات المحددة.")
        return
    
    # Apply filters to dataframe (مواد اوليه and اسم المورد)
    if raw_material and raw_material != "الكل":
        if "مواد اوليه" in df.columns:
            df = df[df["مواد اوليه"] == raw_material]
    
    if selected_suppliers and len(selected_suppliers) > 0:
        if "اسم المورد" in df.columns:
            df = df[df["اسم المورد"].isin(selected_suppliers)]
    
    # Column Search
    search_col, search_term = create_column_search(df)
    if search_col and search_term:
        df = apply_column_search(df, search_col, search_term)
        if df.empty:
            st.info("🔍 لا توجد نتائج بعد تطبيق البحث.")
            return
    
    # Display simple header
    st.markdown(f'<h3 class="hsec">📊 {display_name}</h3>', unsafe_allow_html=True)
    
    # Display Data
    st.markdown('<div class="card soft">', unsafe_allow_html=True)
    
    # Remove ID columns for display
    df_display = df.drop(
        columns=[c for c in df.columns if "id" in c.lower()],
        errors="ignore"
    )
    
    # Remove columns where ALL values are NaN
    df_display = df_display.dropna(axis=1, how='all')
    
    # Reorder columns - ALWAYS show مواد اوليه and اسم المورد first
    if type_key == "financial_report":
        desired_order = [
            "مواد اوليه",
            "اسم المورد",
            "رقم الفاتورة",
            "تاريخ الفاتورة",
            "المبلغ",
            "كميه زجاج متر مربع",
            "كميه المونيوم طن",
            "كميه اكسسوار",
            "كميه ستيل طن",
            "مجموع الكمية لكل مشروع ومورد",
            "مجموع المبلغ لكل مشروع ومورد"
        ]
        ordered_cols = [col for col in desired_order if col in df_display.columns]
        remaining_cols = [col for col in df_display.columns if col not in ordered_cols]
        df_display = df_display[ordered_cols + remaining_cols]
    
    # Reorder columns for invoices - ALWAYS show مواد اوليه and اسم المورد first
    if type_key == "invoices":
        desired_order = [
            "مواد اوليه",
            "اسم المورد",
            "رقم الفاتورة",
            "تاريخ الفاتورة",
            "المبلغ",
            "الكمية",
            "رابط نسخة الفاتورة"
        ]
        ordered_cols = [col for col in desired_order if col in df_display.columns]
        remaining_cols = [col for col in df_display.columns if col not in ordered_cols]
        df_display = df_display[ordered_cols + remaining_cols]
    
    # Configure column display with proper widths and link columns
    column_config = {}
    
    # Set link columns to display as clickable links
    for col in df_display.columns:
        if "رابط" in str(col):
            column_config[col] = st.column_config.LinkColumn(
                label=col,
                display_text="🔗 عرض الفاتورة"
            )
    
    # Display dataframe with proper configuration
    st.dataframe(
        df_display,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=600  # Fixed height for better scrolling
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show data summary
    st.markdown(f"**إجمالي الصفوف:** {len(df_display)}")
    
    # Export Title
    title_export = compose_export_title(
        company_name,
        project_name,
        display_name,
        date_from,
        date_to
    )
    
    # Download Buttons
    st.markdown("### 📥 تنزيل البيانات")
    
    col1, col2 = st.columns(2)
    
    with col1:
        xlsx_bytes = make_excel_bytes(df_display, "البيانات", title_export, put_logo=True)
        if xlsx_bytes:
            st.download_button(
                "📊 تنزيل Excel",
                xlsx_bytes,
                file_name=safe_filename(f"{display_name}_{company_name}_{project_name}.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    with col2:
        pdf_df = format_numbers_for_display(df_display)
        pdf_bytes = make_pdf_bytes(pdf_df, title_export)
        st.download_button(
            "📑 تنزيل PDF",
            pdf_bytes,
            file_name=safe_filename(f"{display_name}_{company_name}_{project_name}.pdf"),
            mime="application/pdf",
            use_container_width=True
        )


if __name__ == "__main__":
    main()