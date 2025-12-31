import streamlit as st
import pandas as pd
from db.connection import fetch_companies, fetch_projects_by_company
from typing import Optional, Tuple

# =========================================================
# Company Dropdown with Search
# =========================================================

def create_company_dropdown(conn) -> Optional[str]:
    """إنشاء قائمة منسدلة للشركات مع بحث"""
    companies_df = fetch_companies(conn)
    
    if companies_df.empty:
        st.info("لا توجد شركات في قاعدة البيانات.")
        return None
    
    companies = (
        companies_df["اسم الشركة"]
        .dropna()
        .drop_duplicates()
        .sort_values(key=lambda s: s.str.lower())
        .tolist()
    )
    
    # Search box
    query = st.text_input(
        "🔍 ابحث عن الشركة",
        value="",
        placeholder="اكتب اسم الشركة...",
        key="company_search"
    )
    
    # Filter companies based on search
    if query:
        q = str(query).strip().lower()
        filtered = [c for c in companies if q in c.lower()]
    else:
        filtered = companies
    
    if not filtered:
        st.info(f"لا توجد شركات تحتوي على «{query}»" if query else "لا توجد شركات.")
        return None
    
    return st.selectbox(
        "اختر الشركة",
        options=filtered,
        index=0 if filtered else None,
        placeholder="— اختر الشركة —"
    )


# =========================================================
# Project Dropdown
# =========================================================

def create_project_dropdown(conn, company_name: str) -> Optional[str]:
    """إنشاء قائمة منسدلة للمشاريع بناءً على الشركة"""
    if not company_name:
        return None
    
    projects_df = fetch_projects_by_company(conn, company_name)
    
    if projects_df.empty:
        st.info(f"لا توجد مشاريع للشركة: {company_name}")
        return None
    
    projects = projects_df["اسم المشروع"].tolist()
    
    return st.selectbox(
        "اختر المشروع",
        options=projects,
        index=0 if projects else None,
        placeholder="— اختر المشروع —"
    )


# =========================================================
# Raw Material Dropdown
# =========================================================

def create_raw_material_dropdown(conn) -> Optional[str]:
    """إنشاء قائمة منسدلة لأنواع المواد الأولية"""
    try:
        resp = conn.table("suppliers").select("مواد اوليه").execute()
        df = pd.DataFrame(resp.data or [])
        
        if df.empty or "مواد اوليه" not in df.columns:
            st.info("لا توجد مواد أولية متاحة.")
            return None
        
        raw_materials = (
            df["مواد اوليه"]
            .dropna()
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        
        if not raw_materials:
            st.info("لا توجد مواد أولية متاحة.")
            return None
        
        return st.selectbox(
            "🔧 اختر نوع المادة الأولية",
            options=["الكل"] + raw_materials,
            index=0,
            placeholder="— اختر —"
        )
        
    except Exception as e:
        st.info(f"حدث خطأ أثناء جلب المواد الأولية: {e}")
        return None


# =========================================================
# Data Type Dropdown
# =========================================================

def create_type_dropdown() -> Tuple[str, str]:
    """إنشاء قائمة منسدلة لنوع البيانات"""
    display_to_key = {
        "📊 تقرير مالي (Financial Report)": "financial_report",
        "📄 فواتير (Invoices)": "invoices",
    }
    
    display_list = list(display_to_key.keys())
    
    display_choice = st.selectbox(
        "اختر نوع البيانات",
        options=display_list,
        index=0,
        placeholder="— اختر النوع —"
    )
    
    return display_choice, display_to_key.get(display_choice)


# =========================================================
# Date Range Filters
# =========================================================

def create_date_range() -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """إنشاء فلاتر نطاق التاريخ"""
    col1, col2 = st.columns(2)
    
    with col1:
        date_from = st.date_input(
            "📅 من تاريخ",
            value=None,
            format="YYYY-MM-DD",
            key="date_from"
        )
    
    with col2:
        date_to = st.date_input(
            "📅 إلى تاريخ",
            value=None,
            format="YYYY-MM-DD",
            key="date_to"
        )
    
    # Convert to datetime
    d_from = pd.to_datetime(date_from) if date_from else None
    d_to = pd.to_datetime(date_to) if date_to else None
    
    return d_from, d_to


# =========================================================
# Column Search
# =========================================================

def create_column_search(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """إنشاء بحث داخل عمود محدد"""
    if df is None or df.empty:
        return None, None
    
    col = st.selectbox(
        "🔍 اختر عمودًا للبحث",
        options=df.columns.tolist(),
        index=0
    )
    
    term = st.text_input(
        "كلمة البحث",
        placeholder="ابحث في العمود المحدد..."
    )
    
    return col, term if term else None