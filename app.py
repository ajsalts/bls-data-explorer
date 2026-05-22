import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page config
st.set_page_config(page_title="Strategic Geo-Pay Tool", layout="wide")

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
    'WI': 93.0, 'WY': 92.8, 'US': 100.0, 'DC': 148.7, 'PR': 100.0, 'VI': 100.0, 'GU': 100.0
}

@st.cache_data
def load_bls_data():
    df = pd.read_csv('cleaned_full_bls_data.csv') 
    area_mapping = {1: 'National', 2: 'State', 4: 'Metro Area', 6: 'Non-Metro'}
    df['AREA_TYPE_LABEL'] = df['AREA_TYPE'].map(area_mapping)
    return df

df_bls = load_bls_data()

# --- SIDEBAR: GEOGRAPHY & JOB ---
st.sidebar.header("1. Locations & Roles")
all_areas = sorted(df_bls['AREA_TITLE'].unique())
selected_areas = st.sidebar.multiselect("Select Areas", all_areas, default=[a for a in all_areas if "San Francisco" in a or "Boulder" in a][:2])
search_query = st.sidebar.text_input("Job Title Search", "Data Scientist")
baseline_area = st.sidebar.selectbox("Baseline Area (Anchor)", options=selected_areas if selected_areas else all_areas)

st.sidebar.divider()
st.sidebar.header("2. Benchmark Settings")
col_source = st.sidebar.radio("COL Data Source", options=["MERIC (State)", "BEA (Price Parity)", "EPI (Family Budget)"])

# --- EPI ENHANCEMENT: DECODER RING ---
family_map = {
    "1p0c": "1 Adult, 0 Children", "1p1c": "1 Adult, 1 Child", "1p2c": "1 Adult, 2 Children",
    "2p0c": "2 Adults, 0 Children", "2p2c": "2 Adults, 2 Children"
}

if col_source == "EPI (Family Budget)" and os.path.exists("epi_data.csv"):
    epi_df = pd.read_csv("epi_data.csv", skiprows=1)
    available_codes = sorted(epi_df['Family'].unique())
    friendly_options = [family_map.get(code, code) for code in available_codes]
    
    selected_friendly = st.sidebar.selectbox("Family Profile", options=friendly_options)
    # Map back to code
    selected_family = [code for code, name in family_map.items() if name == selected_friendly][0]
    
    epi_filtered = epi_df[epi_df['Family'] == selected_family].copy()
    total_col = 'Total.1' if 'Total.1' in epi_filtered.columns else 'Total'
    
    epi_clean = pd.DataFrame({
        'Clean_Name': epi_filtered['Areaname'].str.replace(" MSA", "").str.strip(),
        'COL_VAL': pd.to_numeric(epi_filtered[total_col], errors='coerce')
    }).dropna()
    
    df_bls = pd.merge(df_bls, epi_clean, left_on='AREA_TITLE', right_on='Clean_Name', how='left')
    df_bls['COL_INDEX'] = df_bls['COL_VAL']

# Fallback/Other COL sources
if 'COL_INDEX' not in df_bls.columns:
    df_bls['COL_INDEX'] = df_bls['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)

# --- MAIN UI ---
st.title("⚖️ Geo-Pay Strategy Dashboard")

final_df = df_bls[df_bls['AREA_TITLE'].isin(selected_areas)].copy()
if search_query:
    final_df = final_df[final_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

if not final_df.empty:
    # Calculation Logic
    base_rows = final_df[final_df['AREA_TITLE'] == baseline_area]
    if not base_rows.empty:
        bw, bc = base_rows['A_MEDIAN'].mean(), base_rows['COL_INDEX'].mean()
        final_df['Market Gap %'] = ((final_df['A_MEDIAN'] - bw) / bw) * 100
        final_df['COL Gap %'] = ((final_df['COL_INDEX'] - bc) / bc) * 100
        final_df['Variance'] = final_df['Market Gap %'] - final_df['COL Gap %']

        # Visuals
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(final_df, x='AREA_TITLE', y='Market Gap %', title="Market Wage Differential", color_discrete_sequence=['#1f77b4']), use_container_width=True)
        c2.plotly_chart(px.bar(final_df.drop_duplicates('AREA_TITLE'), x='AREA_TITLE', y='COL Gap %', title="Cost of Living Differential", color_discrete_sequence=['#9467bd']), use_container_width=True)

        st.subheader("Data Comparison Table")
        st.dataframe(final_df[['AREA_TITLE', 'A_MEDIAN', 'Market Gap %', 'COL Gap %', 'Variance']],
                     column_config={"A_MEDIAN": st.column_config.NumberColumn("Salary", format="$%d"),
                                    "Market Gap %": st.column_config.NumberColumn("Market", format="%+.1f%%"),
                                    "COL Gap %": st.column_config.NumberColumn("COL", format="%+.1f%%"),
                                    "Variance": st.column_config.NumberColumn("Variance", format="%+.1f%%")}, 
                     hide_index=True, use_container_width=True)

        # Strategy Box
        v_val = final_df[final_df['AREA_TITLE'] != baseline_area]['Variance'].mean()
        st.divider()
        st.subheader("💡 Employer Strategy Recommendation")
        if v_val < -10:
            st.error(f"**Caution:** Large Negative Variance ({v_val:.1f}%). The market is underpaying relative to cost-of-living. A full market discount may lead to high turnover.")
        elif v_val > 10:
            st.warning(f"**Labor Heat:** Large Positive Variance ({v_val:.1f}%). High competition for talent is driving wages up faster than cost-of-living.")
        else:
            st.success(f"**Balanced:** Small Variance ({v_val:.1f}%). Market wages and cost-of-living are in sync. Standard geo-pay adjustments are safe.")
