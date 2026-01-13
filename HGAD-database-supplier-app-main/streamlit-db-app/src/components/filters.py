import streamlit as st
import pandas as pd
from db.connection import fetch_companies, fetch_projects_by_company, fetch_all_suppliers
from typing import Optional, Tuple, List

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
# Supplier Multiselect Filter (filtered by company, project, material)
# =========================================================

def create_supplier_multiselect(conn, company_name: str, project_name: str, raw_material: str = None) -> List[str]:
    """إنشاء فلتر متعدد الاختيار للموردين حسب الشركة والمشروع والمادة"""
    try:
        if not company_name or not project_name:
            return []
        
        # Get company and project IDs
        company_resp = conn.table("companies").select("id").eq("اسم الشركة", company_name).single().execute()
        if not company_resp.data:
            return []
        company_id = company_resp.data["id"]
        
        project_resp = conn.table("projects").select("id").eq("company_id", company_id).eq("اسم المشروع", project_name).single().execute()
        if not project_resp.data:
            return []
        project_id = project_resp.data["id"]
        
        # Get suppliers from invoices for this company and project
        query = conn.table("invoices").select("supplier_id").eq("company_id", company_id).eq("project_id", project_id)
        invoices_resp = query.execute()
        
        if not invoices_resp.data:
            st.info("لا يوجد موردون لهذه الشركة والمشروع.")
            return []
        
        supplier_ids = list(set([inv["supplier_id"] for inv in invoices_resp.data if inv.get("supplier_id")]))
        
        if not supplier_ids:
            return []
        
        # Get supplier details
        suppliers_resp = conn.table("suppliers").select("id, اسم المورد, مواد اوليه").in_("id", supplier_ids).execute()
        suppliers_df = pd.DataFrame(suppliers_resp.data or [])
        
        if suppliers_df.empty:
            return []
        
        # Filter by raw material if specified
        if raw_material and raw_material != "الكل":
            suppliers_df = suppliers_df[suppliers_df["مواد اوليه"] == raw_material]
        
        if suppliers_df.empty:
            st.info(f"لا يوجد موردون لهذه المادة: {raw_material}")
            return []
        
        # Remove duplicates and sort
        suppliers = (
            suppliers_df["اسم المورد"]
            .dropna()
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        
        if not suppliers:
            return []
        
        selected = st.multiselect(
            "👥 اختر الموردين (اختر واحد أو أكثر، أو اترك فارغاً للكل)",
            options=suppliers,
            default=[],
            placeholder="— اختر الموردين —"
        )
        
        return selected
        
    except Exception as e:
        st.info(f"حدث خطأ أثناء جلب الموردين: {e}")
        return []


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