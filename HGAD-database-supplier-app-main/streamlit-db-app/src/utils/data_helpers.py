import pandas as pd
import re

# =========================================================
# Format Numbers for Display (avoid commas for check numbers)
# =========================================================

def _normalize_name(s: str) -> str:
    """تطبيع أسماء الأعمدة العربية: إزالة المسافات والتشكيل"""
    return re.sub(r'[\s\u0640\u200c\u200d\u200e\u200f]+', '', str(s or ''))


def _plain_number_no_commas(x) -> str:
    """عرض الأرقام بدون فواصل (للشيكات والأرقام المرجعية)"""
    if pd.isna(x):
        return ""
    
    sx = str(x).replace(",", "").strip()
    
    try:
        f = float(sx)
        if float(int(f)) == f:
            return str(int(f))
        
        s = f"{f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    except Exception:
        return str(x)


def format_numbers_for_display(
    df: pd.DataFrame,
    no_comma_cols: list = None
) -> pd.DataFrame:
    """
    تنسيق الأرقام للعرض:
    - الأعمدة المحددة في no_comma_cols أو التي تحتوي على 'شيك' أو 'رقم' تُعرض بدون فواصل
    - باقي الأرقام تُعرض بفواصل الآلاف
    """
    out = df.copy()
    requested = {_normalize_name(c) for c in (no_comma_cols or [])}
    
    for c in out.columns:
        c_norm = _normalize_name(c)
        
        # Check if this column should have no commas
        force_plain = (
            (c_norm in requested) or 
            ("شيك" in c_norm) or 
            ("رقم" in c_norm and "فاتورة" in c_norm)
        )
        
        if force_plain:
            out[c] = out[c].map(_plain_number_no_commas)
            continue
        
        # Format numeric columns with commas
        if pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].map(
                lambda x: "" if pd.isna(x) else f"{float(x):,.2f}"
            )
        else:
            # Try to format string numbers
            def _fmt_cell(v):
                if pd.isna(v):
                    return ""
                s = str(v)
                try:
                    if s.strip().endswith("%"):
                        return s
                    fv = float(s.replace(",", ""))
                    return f"{fv:,.2f}"
                except Exception:
                    return s
            
            out[c] = out[c].map(_fmt_cell)
    
    return out


# =========================================================
# Apply Date Filters
# =========================================================

def apply_date_filter(df: pd.DataFrame, date_from, date_to) -> pd.DataFrame:
    """تطبيق فلتر التاريخ على DataFrame"""
    if df is None or df.empty or (not date_from and not date_to):
        return df
    
    # Find date columns
    date_cols = [
        c for c in df.columns 
        if any(k in str(c) for k in ["تاريخ", "date", "Date"])
    ]
    
    if not date_cols:
        return df
    
    out = df.copy()
    
    for col in date_cols:
        try:
            date_series = pd.to_datetime(out[col], errors="coerce").dt.date
            
            if date_from:
                out = out[date_series >= date_from]
            
            if date_to:
                out = out[date_series <= date_to]
                
        except Exception:
            continue
    
    return out


# =========================================================
# Apply Column Search Filter
# =========================================================

def apply_column_search(
    df: pd.DataFrame,
    column: str,
    search_term: str
) -> pd.DataFrame:
    """تطبيق بحث على عمود محدد"""
    if df is None or df.empty or not column or not search_term:
        return df
    
    if column not in df.columns:
        return df
    
    return df[
        df[column]
        .astype(str)
        .str.contains(str(search_term), case=False, na=False)
    ]


# =========================================================
# Safe Filename Generator
# =========================================================

def safe_filename(s: str) -> str:
    """إنشاء اسم ملف آمن بإزالة الأحرف الخاصة"""
    return (
        (s or "")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
        .replace("*", "-")
        .replace("?", "-")
        .replace('"', "'")
        .replace("<", "(")
        .replace(">", ")")
        .replace("|", "-")
    )


# =========================================================
# Compose Title for Exports
# =========================================================

def compose_export_title(
    company: str,
    project: str,
    data_type: str,
    date_from,
    date_to
) -> str:
    """إنشاء عنوان موحد للتصدير"""
    parts = []
    
    if company:
        parts.append(f"الشركة: {company}")
    
    if project:
        parts.append(f"المشروع: {project}")
    
    if data_type:
        parts.append(f"النوع: {data_type}")
    
    if date_from or date_to:
        parts.append(f"الفترة: {date_from or '—'} ← {date_to or '—'}")
    
    return " | ".join(parts)


# =========================================================
# Format Value for Summary Display
# =========================================================

def format_value(v) -> str:
    """تنسيق قيمة للعرض في الملخصات"""
    try:
        if isinstance(v, str) and v.strip().endswith("%"):
            return v
        
        f = float(str(v).replace(",", ""))
        return f"{f:,.2f}"
        
    except Exception:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return str(v)