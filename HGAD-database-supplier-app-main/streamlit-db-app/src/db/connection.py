import streamlit as st
import pandas as pd
from supabase import create_client, Client
import re

# تهيئة عميل Supabase مرة واحدة
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

# الشركات
def fetch_companies(supabase: Client) -> pd.DataFrame:
    try:
        resp = supabase.table("companies").select("اسم الشركة").execute()
        df = pd.DataFrame(resp.data or [])
        # sort alphabetically
        if not df.empty:
            df = df.drop_duplicates().sort_values("اسم الشركة", key=lambda s: s.str.lower())
        else:
            df = df.drop_duplicates()
        return df
    except Exception:
        return pd.DataFrame(columns=["اسم الشركة"])

# المشاريع بحسب الشركة
def fetch_projects_by_company(supabase: Client, company_name: str) -> pd.DataFrame:
    if not company_name:
        return pd.DataFrame(columns=["اسم المشروع"])
    try:
        company_resp = (
            supabase.table("companies")
            .select("id")
            .eq("اسم الشركة", company_name)
            .single()
            .execute()
        )
        if not company_resp.data:
            return pd.DataFrame(columns=["اسم المشروع"])
        company_id = company_resp.data["id"]

        projects_resp = (
            supabase.table("projects")
            .select('"اسم المشروع"')
            .eq("company_id", company_id)
            .execute()
        )
        df = pd.DataFrame(projects_resp.data or [])
        df = df.rename(columns={'"اسم المشروع"': 'اسم المشروع'})
        return df.drop_duplicates()

    except Exception as e:
        st.caption(f"⚠️ fetch_projects_by_company error: {e}")
        return pd.DataFrame(columns=["اسم المشروع"])

def _get_company_and_project_ids(supabase: Client, company_name: str, project_name: str) -> tuple[int | None, int | None]:
    try:
        company_resp = (
            supabase.table("companies")
            .select("id, اسم الشركة")
            .eq("اسم الشركة", company_name)
            .single()
            .execute()
        )
        if not company_resp.data:
            return None, None
        company_id = company_resp.data["id"]

        project_resp = (
            supabase.table("projects")
            .select('id, company_id, "اسم المشروع"')
            .eq("company_id", company_id)
            .filter('اسم المشروع', 'eq', project_name)
            .single()
            .execute()
        )
        if not project_resp.data:
            return company_id, None
        return company_id, project_resp.data["id"]
    except Exception as e:
        st.caption(f"⚠️ _get_company_and_project_ids error: {e}")
        return None, None

def fetch_suppliers_by_raw_material(supabase: Client, raw_material: str) -> pd.DataFrame:
    """Fetch suppliers filtered by raw material (مواد اوليه)"""
    try:
        resp = supabase.table("suppliers").select("id, اسم المورد, مواد اوليه").eq("مواد اوليه", raw_material).execute()
        df = pd.DataFrame(resp.data or [])
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "اسم المورد", "مواد اوليه"])

def fetch_companies_by_supplier(supabase: Client, supplier_name: str = None, raw_material: str = None) -> pd.DataFrame:
    """Fetch companies filtered by supplier and/or raw material (if needed)"""
    # This assumes a relationship exists between companies and suppliers via projects/invoices
    try:
        if supplier_name:
            # Join invoices, companies, suppliers to get companies for a supplier
            query = (
                supabase.rpc(
                    "custom_companies_by_supplier",
                    {"supplier_name": supplier_name, "raw_material": raw_material}
                )
            )
            resp = query.execute()
            df = pd.DataFrame(resp.data or [])
            return df
        else:
            # fallback to all companies
            return fetch_companies(supabase)
    except Exception:
        return pd.DataFrame(columns=["id", "اسم الشركة"])

