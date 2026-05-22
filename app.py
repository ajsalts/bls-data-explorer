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
    """Loads the core market wage data."""
    try:
        df = pd.read_csv('cleaned_full_bls_data.csv') 
        area_mapping = {
            1: 'National (U.S.)', 2: 'State', 3: 'U.S. Territory', 
            4: 'Metropolitan Area (City/Region)', 6: 'Nonmetropolitan Area'
        }
        df['AREA_TYPE_LABEL'] = df['AREA_TYPE'].map(area_mapping)
        return df
    except Exception as e:
        st.error(f"Error loading BLS data: {e}")
        return pd.DataFrame()

df_bls = load_bls_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("1. Filter Locations")
if not df_bls.empty:
    area_types = df_bls['AREA_TYPE_LABEL'].dropna().unique()
    selected_area_type = st.sidebar.selectbox("Geographic Level", options=area_types, index=list(area_types).index('Metropolitan Area (City/Region)') if 'Metropolitan Area (City/Region)' in area_types else 0)

    filtered_by_type = df_bls[df_bls['AREA_TYPE_LABEL'] == selected_area_type].copy()
    all_areas = sorted(filtered_by_type['AREA_TITLE'].unique())

    # Smart defaults for demo
    default_areas = [a for a in all_areas if any(city in a for city in ["San Francisco", "Boulder", "New York", "Austin"])]
    selected_areas = st.sidebar.multiselect("Select Specific Areas", all_areas, default=default_areas[:3])
    search_query = st.sidebar.text_input("Job Title Search", "Data Scientist")
else:
    st.error("BLS Data file not found.")

st.sidebar.divider()
st.sidebar.header("2. Comp Planning Settings")
baseline_area = st.sidebar.selectbox("Baseline Area (0% Anchor)", options=selected_areas if selected_areas else ["Select Areas First"])

col_source = st.sidebar.radio("COL Data Source", options=["MERIC (State Index)", "BEA (Price Parity)", "EPI (Annual Family Budget)"])

# --- COL LOGIC: EPI FAMILY BUDGET ---
if col_source == "EPI (Annual Family Budget)" and os.path.exists("epi_data.csv"):
    try:
        # EPI CSV often has two header rows. We detect and clean it.
        test_df = pd.read_csv("epi_data.csv", nrows=5)
        skip = 1 if 'case_id' not in test_df.columns else 0
        epi_df = pd.read_csv("epi_data.csv", skiprows=skip)
        
        # Family Type Selection
        family_list = sorted(epi_df['Family'].unique())
        selected_family = st.sidebar.selectbox("EPI Family Type", options=family_list, index=0, help="1p0c = 1 Adult, 0 Child. 2p2c = 2 Adult, 2 Child.")
        
        # Filter for family and get Annual Total
        epi_filtered = epi_df[epi_df['Family'] == selected_family].copy()
        total_col = 'Total.1' if 'Total.1' in epi_filtered.columns else 'Total'
        
        epi_clean = pd.DataFrame({
            'Clean_Name': epi_filtered['Areaname'].astype(str).str.replace(r" MSA", "", regex=True).str.strip(),
            'COL_VAL': pd.to_numeric(epi_filtered[total_col], errors='coerce')
        }).dropna(subset=['COL_VAL']).drop_duplicates(subset=['Clean_Name'])
        
        filtered_by_type = pd.merge(filtered_by_type, epi_clean, left_on='AREA_TITLE', right_on='Clean_Name', how='left')
        filtered_by_type['COL_INDEX'] = filtered_by_type['COL_VAL']
    except Exception as e:
        st.sidebar.error(f"EPI Processing Error: {e}")

# --- COL LOGIC: BEA PRICE PARITY ---
elif col_source == "BEA (Price Parity)" and os.path.exists("bea_data.csv"):
    try:
        bea_df = pd.read_csv("bea_data.csv").dropna(axis=1, how='all')
        name_s = bea_df.iloc[:, 1].squeeze()
        val_s = bea_df.iloc[:, -1].squeeze()
        bea_clean = pd.DataFrame({
            'Clean_Name': name_s.astype(str).str.replace(r" \(Metropolitan Statistical Area\)", "", regex=True).str.strip(),
            'COL_VAL': pd.to_numeric(val_s, errors='coerce')
        }).dropna(subset=['COL_VAL']).drop_duplicates(subset=['Clean_Name'])
        filtered_by_type = pd.merge(filtered_by_type, bea_clean, left_on='AREA_TITLE', right_on='Clean_Name', how='left')
        filtered_by_type['COL_INDEX'] = filtered_by_type['COL_VAL']
    except Exception as e:
        st.sidebar.error(f"BEA Processing Error: {e}")

# --- FALLBACK: MERIC STATE DATA ---
if 'COL_INDEX' not in filtered_by_type.columns:
    filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)
else:
    filtered_by_type['COL_INDEX'] = filtered_by_type['COL_INDEX'].fillna(filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0))

# --- MAIN APP UI ---
st.title("📊 Strategic Geo-Pay Planner")
st.markdown("Analyze market wage data against cost-of-living benchmarks to build equitable pay bands.")

# Filter by selected areas and search query
final_df = filtered_by_type[filtered_by_type['AREA_TITLE'].isin(selected_areas)].copy()
if search_query:
    final_df = final_df[final_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

if not final_df.empty:
    # 1. High-Level Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Market Wage Comparison")
        fig_wage = px.bar(final_df, x='AREA_TITLE', y='A_MEDIAN', color='A_MEDIAN', 
                          labels={'A_MEDIAN':'Median Annual Wage', 'AREA_TITLE':''},
                          color_continuous_scale='Blues')
        st.plotly_chart(fig_wage, use_container_width=True)
    
    with col2:
        st.subheader("Cost of Living Benchmark")
        # Color based on data source
        color_seq = ['#9467bd'] if col_source == "EPI (Annual Family Budget)" else ['#FFA500']
        fig_col = px.bar(final_df.drop_duplicates('AREA_TITLE'), x='AREA_TITLE', y='COL_INDEX', 
                         labels={'COL_INDEX':'COL Metric', 'AREA_TITLE':''},
                         color_discrete_sequence=color_seq)
        st.plotly_chart(fig_col, use_container_width=True)

    # 2. Detailed Pay Differential Calculator
    st.divider()
    st.subheader(f"🎯 Geographic Pay Differentials (Anchor: {baseline_area})")
    
    base_rows = final_df[final_df['AREA_TITLE'] == baseline_area]
    if not base_rows.empty:
        base_wage = base_rows['A_MEDIAN'].mean()
        base_col = base_rows['COL_INDEX'].mean()
        
        final_df['Market Gap %'] = ((final_df['A_MEDIAN'] - base_wage) / base_wage) * 100
        final_df['COL Gap %'] = ((final_df['COL_INDEX'] - base_col) / base_col) * 100
        final_df['Gap Variance'] = final_df['Market Gap %'] - final_df['COL Gap %']

        st.dataframe(
            final_df[['AREA_TITLE', 'OCC_TITLE', 'A_MEDIAN', 'COL_INDEX', 'Market Gap %', 'COL Gap %', 'Gap Variance']],
            column_config={
                "AREA_TITLE": "Region",
                "OCC_TITLE": "Job Title",
                "A_MEDIAN": st.column_config.NumberColumn("Market Wage", format="$%d"),
                "COL_INDEX": st.column_config.NumberColumn("COL Value", format="$%d" if col_source == "EPI (Annual Family Budget)" else "%.1f"),
                "Market Gap %": st.column_config.NumberColumn("Market vs Anchor", format="%+.1f%%"),
                "COL Gap %": st.column_config.NumberColumn("COL vs Anchor", format="%+.1f%%"),
                "Gap Variance": st.column_config.NumberColumn("Pay Strategy Variance", format="%+.1f%%", help="Positive means market wages are rising faster than local COL. Negative means COL is outpacing local wages.")
            },
            hide_index=True, use_container_width=True
        )
        
        st.info("💡 **Strategy Hint:** If 'Pay Strategy Variance' is highly negative, you may need a 'Cost of Living Adjustment' (COLA) to remain competitive, even if market wages haven't shifted yet.")
    else:
        st.warning(f"Please include the Baseline Area ({baseline_area}) in your 'Select Specific Areas' filter to see comparisons.")
else:
    st.info("👈 Select locations and search for a job title in the sidebar to begin analysis.")
