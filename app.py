import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re

# Set page config
st.set_page_config(page_title="Strategic Geo-Pay Planner", layout="wide")

# --- HELPER: ROBUST NAME CLEANER ---
def clean_geo_name(name):
    """Normalizes names like 'San Francisco-Oakland, CA' to 'San Francisco, CA'"""
    if pd.isna(name): return ""
    name = str(name).split(" HUD")[0].split(" MSA")[0].strip()
    if "," in name:
        parts = name.split(",")
        city_part = parts[0].split("-")[0].strip() # Take first city in a hyphenated list
        state_part = parts[1].strip().split(" ")[0].split("-")[0].strip() # Take first state
        return f"{city_part}, {state_part}"
    return name

# --- DATA SOURCE: MERIC (State-Level Fallback) ---
MERIC_COL_INDEX = {
    'AL': 88.1, 'AK': 125.1, 'AZ': 104.5, 'AR': 89.9, 'CA': 138.5, 'CO': 106.9, 
    'CT': 114.3, 'DE': 103.5, 'FL': 102.3, 'GA': 91.0, 'HI': 180.3, 'ID': 100.3, 
    'IL': 91.5, 'IN': 90.0, 'IA': 90.1, 'KS': 87.4, 'KY': 93.8, 'LA': 92.0, 
    'ME': 111.5, 'MD': 116.1, 'MA': 148.0, 'MI': 91.2, 'MN': 94.4, 'MS': 85.3, 
    'MO': 88.4, 'MT': 103.7, 'NE': 92.4, 'NV': 101.3, 'NH': 115.0, 'NJ': 114.2, 
    'NM': 93.3, 'NY': 126.5, 'NC': 96.1, 'ND': 95.3, 'OH': 92.2, 'OK': 86.4, 
    'OR': 115.1, 'PA': 98.2, 'RI': 113.1, 'SC': 96.5, 'SD': 93.8, 'TN': 90.2, 
    'TX': 92.5, 'UT': 102.1, 'VT': 115.2, 'VA': 103.1, 'WA': 115.7, 'WV': 88.5, 
    'WI': 93.0, 'WY': 92.8, 'US': 100.0, 'DC': 148.7
}

@st.cache_data
def load_bls_data():
    try:
        df = pd.read_csv('cleaned_full_bls_data.csv') 
        df['JOIN_NAME'] = df['AREA_TITLE'].apply(clean_geo_name)
        return df
    except:
        return pd.DataFrame()

df_bls = load_bls_data()

# --- SIDEBAR ---
st.sidebar.header("1. Filter Locations")
all_areas = sorted(df_bls['AREA_TITLE'].unique()) if not df_bls.empty else []
selected_areas = st.sidebar.multiselect("Select Areas", all_areas, default=all_areas[:2] if all_areas else [])
search_query = st.sidebar.text_input("Job Title Search", "Data Scientist")

st.sidebar.divider()
st.sidebar.header("2. Comp Planning Settings")
baseline_area = st.sidebar.selectbox("Baseline Area (Anchor)", options=selected_areas if selected_areas else ["Select Areas First"])
col_source = st.sidebar.radio("COL Data Source", options=["MERIC (State)", "EPI (Family Budget)"])

# --- DATA PROCESSING: EPI ---
col_mapped = False
if col_source == "EPI (Family Budget)" and os.path.exists("epi_data.csv"):
    try:
        epi_df = pd.read_csv("epi_data.csv", skiprows=1)
        family_types = sorted(epi_df['Family'].unique())
        selected_family = st.sidebar.selectbox("Select Family Profile", options=family_types, index=0)
        
        epi_filtered = epi_df[epi_df['Family'] == selected_family].copy()
        total_col = [c for c in epi_filtered.columns if 'Total' in c][-1]
        
        epi_clean = pd.DataFrame({
            'JOIN_NAME': epi_filtered['Areaname'].apply(clean_geo_name),
            'ANNUAL_BUDGET': pd.to_numeric(epi_filtered[total_col], errors='coerce')
        }).dropna().drop_duplicates('JOIN_NAME')
        
        # Filter BLS data for selection
        final_df = df_bls[df_bls['AREA_TITLE'].isin(selected_areas)].copy()
        if search_query:
            final_df = final_df[final_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]
            
        # Merge on cleaned names
        final_df = pd.merge(final_df, epi_clean, on='JOIN_NAME', how='left')
        
        # Normalization
        base_join_name = clean_geo_name(baseline_area)
        if base_join_name in epi_clean['JOIN_NAME'].values:
            base_budget = epi_clean[epi_clean['JOIN_NAME'] == base_join_name]['ANNUAL_BUDGET'].values[0]
            final_df['COL_INDEX'] = (final_df['ANNUAL_BUDGET'] / base_budget) * 100
            col_mapped = True
    except Exception as e:
        st.sidebar.error(f"EPI Error: {e}")

# --- FALLBACK ---
if col_source == "MERIC (State)" or not col_mapped:
    final_df = df_bls[df_bls['AREA_TITLE'].isin(selected_areas)].copy()
    if search_query:
        final_df = final_df[final_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]
    final_df['COL_INDEX'] = final_df['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)
    # Re-normalize MERIC to Anchor
    anchor_meric = MERIC_COL_INDEX.get(df_bls[df_bls['AREA_TITLE']==baseline_area]['PRIM_STATE'].iloc[0], 100.0) if baseline_area in all_areas else 100.0
    final_df['COL_INDEX'] = (final_df['COL_INDEX'] / anchor_meric) * 100

# --- UI OUTPUT ---
st.title("📊 Strategic Geo-Pay Explorer")
if not final_df.empty:
    # Calculations
    base_rows = final_df[final_df['AREA_TITLE'] == baseline_area]
    if not base_rows.empty:
        bw = base_rows['A_MEDIAN'].mean()
        final_df['Market Gap %'] = ((final_df['A_MEDIAN'] - bw) / bw) * 100
        final_df['COL Gap %'] = (final_df['COL_INDEX'] - 100.0)
        final_df['Gap Variance'] = final_df['Market Gap %'] - final_df['COL Gap %']

        # Charts
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(final_df, x='AREA_TITLE', y='A_MEDIAN', title="Market Wages"), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(final_df, x='AREA_TITLE', y='COL_INDEX', title=f"COL Index (Anchor={baseline_area})"), use_container_width=True)

        st.dataframe(
            final_df[['AREA_TITLE', 'OCC_TITLE', 'A_MEDIAN', 'Market Gap %', 'COL Gap %', 'Gap Variance']],
            column_config={
                "A_MEDIAN": st.column_config.NumberColumn("Market Wage", format="$%d"),
                "Market Gap %": st.column_config.NumberColumn("Market Gap", format="%+.1f%%"),
                "COL Gap %": st.column_config.NumberColumn("COL Gap", format="%+.1f%%"),
                "Gap Variance": st.column_config.NumberColumn("Variance", format="%+.1f%%")
            }, hide_index=True, use_container_width=True
        )
