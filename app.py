import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page config
st.set_page_config(page_title="Geo-Pay Banding Tool", layout="wide")

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
    area_mapping = {
        1: 'National (U.S.)', 2: 'State', 3: 'U.S. Territory', 
        4: 'Metropolitan Area (City/Region)', 6: 'Nonmetropolitan Area'
    }
    df['AREA_TYPE_LABEL'] = df['AREA_TYPE'].map(area_mapping)
    return df

df_bls = load_bls_data()

# --- SIDEBAR ---
st.sidebar.header("1. Filter Locations")
area_types = df_bls['AREA_TYPE_LABEL'].dropna().unique()
selected_area_type = st.sidebar.selectbox("Geographic Level", options=area_types, index=3)

filtered_by_type = df_bls[df_bls['AREA_TYPE_LABEL'] == selected_area_type].copy()
all_areas = sorted(filtered_by_type['AREA_TITLE'].unique())

default_areas = [a for a in all_areas if "San Francisco" in a or "Boulder" in a or "New York" in a][:3]
selected_areas = st.sidebar.multiselect("Select Specific Areas", all_areas, default=default_areas)
search_query = st.sidebar.text_input("Job Title Search", "Data Scientist")

st.sidebar.divider()
st.sidebar.header("2. Comp Planning Settings")
baseline_area = st.sidebar.selectbox("Baseline Area (0% Anchor)", options=selected_areas if selected_areas else all_areas)

col_source = st.sidebar.radio("COL Data Source", options=["MERIC (State)", "BEA (City-Level)"])

# --- THE FIX: NEW BEA LOGIC ---
if col_source == "BEA (City-Level)" and os.path.exists("bea_data.csv"):
    try:
        # Load and immediately drop completely empty columns
        bea_df = pd.read_csv("bea_data.csv").dropna(axis=1, how='all')
        
        # Squeeze forces 1-column DataFrames into Series to avoid the "arg must be a list" error
        name_series = bea_df.iloc[:, 1].squeeze()
        val_series = bea_df.iloc[:, -1].squeeze()

        # Build clean mapping
        bea_clean = pd.DataFrame({
            'Clean_Name': name_series.astype(str).str.replace(r" \(Metropolitan Statistical Area\)", "", regex=True).str.strip(),
            'COL_INDEX': pd.to_numeric(val_series, errors='coerce')
        })

        # Remove the footer/metadata rows (BEA usually puts text in the last column that becomes NaN)
        bea_clean = bea_clean.dropna(subset=['COL_INDEX'])
        bea_clean = bea_clean.drop_duplicates(subset=['Clean_Name'])

        # Merge
        filtered_by_type = pd.merge(filtered_by_type, bea_clean, left_on='AREA_TITLE', right_on='Clean_Name', how='left')
        filtered_by_type['COL_INDEX'] = filtered_by_type['COL_INDEX'].fillna(100.0)

    except Exception as e:
        st.error(f"BEA Merge Error: {e}")
        filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)
else:
    filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)

# --- FILTER & CALCULATE ---
final_df = filtered_by_type[filtered_by_type['AREA_TITLE'].isin(selected_areas)].copy()
if search_query:
    final_df = final_df[final_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

# --- UI DISPLAY ---
st.title("📊 Geo-Pay Banding Explorer")

if not final_df.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Market Wages")
        st.plotly_chart(px.bar(final_df, x='AREA_TITLE', y='A_MEDIAN', color='A_MEDIAN'), use_container_width=True)
    with c2:
        st.subheader("Cost of Living")
        st.plotly_chart(px.bar(final_df.drop_duplicates('AREA_TITLE'), x='AREA_TITLE', y='COL_INDEX'), use_container_width=True)

    st.divider()
    st.subheader(f"🎯 Pay Differentials vs {baseline_area}")
    
    base_rows = final_df[final_df['AREA_TITLE'] == baseline_area]
    if not base_rows.empty:
        bw, bc = base_rows['A_MEDIAN'].mean(), base_rows['COL_INDEX'].mean()
        final_df['Market Gap'] = ((final_df['A_MEDIAN'] - bw) / bw) * 100
        final_df['COL Gap'] = ((final_df['COL_INDEX'] - bc) / bc) * 100

        st.dataframe(
            final_df[['AREA_TITLE', 'OCC_TITLE', 'A_MEDIAN', 'COL_INDEX', 'Market Gap', 'COL Gap']],
            column_config={
                "A_MEDIAN": st.column_config.NumberColumn("Wage", format="$%d"),
                "Market Gap": st.column_config.NumberColumn("Market %", format="%+.1f%%"),
                "COL Gap": st.column_config.NumberColumn("COL %", format="%+.1f%%")
            }, hide_index=True, use_container_width=True
        )
else:
    st.info("Select regions and search for a job to begin.")
