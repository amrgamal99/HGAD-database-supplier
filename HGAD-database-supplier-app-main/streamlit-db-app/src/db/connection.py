import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional

# =========================================================
# Supabase Connection
# =========================================================

@st.cache_resource
def get_db_connection() -> Client | None:
    try:
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
        supabase_client: Client = create_client(url, key)
        return supabase_client
    except Exception as e:
        st.error(f"فشل تهيئة عميل Supabase. راجع secrets. الخطأ: {e}")
        return None


# =========================================================
# Fetch Companies
# =========================================================

def fetch_companies(supabase: Client) -> pd.DataFrame:
    """جلب قائمة الشركات مرتبة أبجديًا"""
    try:
        resp = supabase.table("companies").select("id, اسم الشركة").execute()
        df = pd.DataFrame(resp.data or [])
        if not df.empty:
            df = df.drop_duplicates().sort_values("اسم الشركة", key=lambda s: s.str.lower())
        return df
    except Exception as e:
        st.caption(f"⚠️ خطأ في جلب الشركات: {e}")
        return pd.DataFrame(columns=["id", "اسم الشركة"])


# =========================================================
# Fetch Projects by Company
# =========================================================

def fetch_projects_by_company(supabase: Client, company_name: str) -> pd.DataFrame:
    """جلب المشاريع بناءً على اسم الشركة"""
    if not company_name:
        return pd.DataFrame(columns=["id", "اسم المشروع"])
    
    try:
        # Get company ID
        company_resp = (
            supabase.table("companies")
            .select("id")
            .eq("اسم الشركة", company_name)
            .single()
            .execute()
        )
        
        if not company_resp.data:
            return pd.DataFrame(columns=["id", "اسم المشروع"])
        
        company_id = company_resp.data["id"]
        
        # Get projects
        projects_resp = (
            supabase.table("projects")
            .select("id, اسم المشروع")
            .eq("company_id", company_id)
            .execute()
        )
        
        df = pd.DataFrame(projects_resp.data or [])
        return df.drop_duplicates() if not df.empty else df
        
    except Exception as e:
        st.caption(f"⚠️ خطأ في جلب المشاريع: {e}")
        return pd.DataFrame(columns=["id", "اسم المشروع"])


# =========================================================
# Fetch Suppliers by Raw Material
# =========================================================

def fetch_suppliers_by_raw_material(supabase: Client, raw_material: str) -> pd.DataFrame:
    """جلب الموردين حسب نوع المادة الأولية"""
    try:
        resp = (
            supabase.table("suppliers")
            .select("id, اسم المورد, مواد اوليه")
            .eq("مواد اوليه", raw_material)
            .execute()
        )
        df = pd.DataFrame(resp.data or [])
        return df
    except Exception as e:
        st.caption(f"⚠️ خطأ في جلب الموردين: {e}")
        return pd.DataFrame(columns=["id", "اسم المورد", "مواد اوليه"])


# =========================================================
# Fetch Financial Report (View)
# =========================================================

def fetch_financial_report(
    supabase: Client,
    company_name: str,
    project_name: str,
    date_from=None,
    date_to=None,
    raw_material: str = None
) -> pd.DataFrame:
    """جلب التقرير المالي من الـ VIEW مع إمكانية التصفية"""
    try:
        # Get IDs
        company_resp = (
            supabase.table("companies")
            .select("id")
            .eq("اسم الشركة", company_name)
            .single()
            .execute()
        )
        
        if not company_resp.data:
            return pd.DataFrame()
        
        company_id = company_resp.data["id"]
        
        project_resp = (
            supabase.table("projects")
            .select("id")
            .eq("company_id", company_id)
            .eq("اسم المشروع", project_name)
            .single()
            .execute()
        )
        
        if not project_resp.data:
            return pd.DataFrame()
        
        project_id = project_resp.data["id"]
        
        # Query financial_report view
        query = (
            supabase.table("financial_report")
            .select("*")
            .eq("company_id", company_id)
            .eq("project_id", project_id)
        )
        
        resp = query.execute()
        df = pd.DataFrame(resp.data or [])
        
        if df.empty:
            return df
        
        # Apply date filters
        if date_from or date_to:
            if "تاريخ الفاتورة" in df.columns:
                df["تاريخ الفاتورة"] = pd.to_datetime(df["تاريخ الفاتورة"], errors="coerce")
                if date_from:
                    df = df[df["تاريخ الفاتورة"] >= pd.to_datetime(date_from)]
                if date_to:
                    df = df[df["تاريخ الفاتورة"] <= pd.to_datetime(date_to)]
        
        # Apply raw material filter if provided
        if raw_material:
            # Get supplier IDs for this raw material
            suppliers_df = fetch_suppliers_by_raw_material(supabase, raw_material)
            if not suppliers_df.empty:
                supplier_ids = suppliers_df["id"].tolist()
                df = df[df["supplier_id"].isin(supplier_ids)]
        
        return df
        
    except Exception as e:
        st.caption(f"⚠️ خطأ في جلب التقرير المالي: {e}")
        return pd.DataFrame()


# =========================================================
# Fetch Invoices (Raw Data)
# =========================================================

def fetch_invoices_data(
    supabase: Client,
    company_name: str,
    project_name: str,
    date_from=None,
    date_to=None,
    raw_material: str = None
) -> pd.DataFrame:
    """جلب الفواتير الخام مع إمكانية التصفية"""
    try:
        # Get IDs
        company_resp = (
            supabase.table("companies")
            .select("id")
            .eq("اسم الشركة", company_name)
            .single()
            .execute()
        )
        
        if not company_resp.data:
            return pd.DataFrame()
        
        company_id = company_resp.data["id"]
        
        project_resp = (
            supabase.table("projects")
            .select("id")
            .eq("company_id", company_id)
            .eq("اسم المشروع", project_name)
            .single()
            .execute()
        )
        
        if not project_resp.data:
            return pd.DataFrame()
        
        project_id = project_resp.data["id"]
        
        # Build query
        query = (
            supabase.table("invoices")
            .select("""
                *,
                companies!inner(اسم الشركة),
                projects!inner(اسم المشروع),
                suppliers!inner(اسم المورد, مواد اوليه)
            """)
            .eq("company_id", company_id)
            .eq("project_id", project_id)
        )
        
        resp = query.execute()
        df = pd.DataFrame(resp.data or [])
        
        if df.empty:
            return df
        
        # Flatten nested columns
        if "companies" in df.columns:
            df["اسم الشركة"] = df["companies"].apply(lambda x: x.get("اسم الشركة") if isinstance(x, dict) else "")
            df = df.drop(columns=["companies"])
        
        if "projects" in df.columns:
            df["اسم المشروع"] = df["projects"].apply(lambda x: x.get("اسم المشروع") if isinstance(x, dict) else "")
            df = df.drop(columns=["projects"])
        
        if "suppliers" in df.columns:
            df["اسم المورد"] = df["suppliers"].apply(lambda x: x.get("اسم المورد") if isinstance(x, dict) else "")
            df["مواد اوليه"] = df["suppliers"].apply(lambda x: x.get("مواد اوليه") if isinstance(x, dict) else "")
            df = df.drop(columns=["suppliers"])
        
        # Apply date filters
        if date_from or date_to:
            if "تاريخ الفاتورة" in df.columns:
                df["تاريخ الفاتورة"] = pd.to_datetime(df["تاريخ الفاتورة"], errors="coerce")
                if date_from:
                    df = df[df["تاريخ الفاتورة"] >= pd.to_datetime(date_from)]
                if date_to:
                    df = df[df["تاريخ الفاتورة"] <= pd.to_datetime(date_to)]
        
        # Apply raw material filter
        if raw_material and "مواد اوليه" in df.columns:
            df = df[df["مواد اوليه"] == raw_material]
        
        return df
        
    except Exception as e:
        st.caption(f"⚠️ خطأ في جلب الفواتير: {e}")
        return pd.DataFrame()