import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page config
st.set_page_config(page_title="Strategic Geo-Pay Planner", layout="wide")

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
    try:
        df = pd.read_csv('cleaned_full_bls_data.csv') 
        area_mapping = {
            1: 'National (U.S.)', 2: 'State', 3: 'U.S. Territory', 
            4: 'Metropolitan Area (City/Region)', 6: 'Nonmetropolitan Area'
        }
        df['AREA_TYPE_LABEL'] = df['AREA_TYPE'].map(area_mapping)
        return df
    except:
        return pd.DataFrame()

df_bls = load_bls_data()

# --- SIDEBAR ---
st.sidebar.header("1. Filter Locations")
area_types = df_bls['AREA_TYPE_LABEL'].dropna().unique()
selected_area_type = st.sidebar.selectbox("Geographic Level", options=area_types, index=3)
filtered_by_type = df_bls[df_bls['AREA_TYPE_LABEL'] == selected_area_type].copy()
all_areas = sorted(filtered_by_type['AREA_TITLE'].unique())
default_areas = [a for a in all_areas if any(city in a for city in ["San Francisco", "Boulder", "New York", "Austin"])]
selected_areas = st.sidebar.multiselect("Select Specific Areas", all_areas, default=default_areas[:2])
search_query = st.sidebar.text_input("Job Title Search", "Data Scientist")

st.sidebar.divider()
st.sidebar.header("2. Comp Planning Settings")
baseline_area = st.sidebar.selectbox("Baseline Area (Anchor)", options=selected_areas if selected_areas else ["Select Areas First"])
col_source = st.sidebar.radio("COL Data Source", options=["MERIC (State)", "BEA (Price Parity)", "EPI (Family Budget)"])

# --- DATA PROCESSING ---
if col_source == "EPI (Family Budget)" and os.path.exists("epi_data.csv"):
    try:
        epi_df = pd.read_csv("epi_data.csv", skiprows=1)
        family_types = sorted(epi_df['Family'].unique())
        selected_family = st.sidebar.selectbox("Select Family Profile", options=family_types, index=0)
        epi_filtered = epi_df[epi_df['Family'] == selected_family].copy()
        total_col = [c for c in epi_filtered.columns if 'Total' in c][-1]
        epi_clean = pd.DataFrame({
            'Clean_Name': epi_filtered['Areaname'].astype(str).str.replace(r" MSA", "", regex=True).str.strip(),
            'ANNUAL_BUDGET': pd.to_numeric(epi_filtered[total_col], errors='coerce')
        }).dropna()
        filtered_by_type = pd.merge(filtered_by_type, epi_clean, left_on='AREA_TITLE', right_on='Clean_Name', how='left')
        if baseline_area in epi_clean['Clean_Name'].values:
            base_val = epi_clean[epi_clean['Clean_Name'] == baseline_area]['ANNUAL_BUDGET'].values[0]
            filtered_by_type['COL_INDEX'] = (filtered_by_type['ANNUAL_BUDGET'] / base_val) * 100
    except: pass

elif col_source == "BEA (Price Parity)" and os.path.exists("bea_data.csv"):
    try:
        bea_df = pd.read_csv("bea_data.csv").dropna(axis=1, how='all')
        bea_clean = pd.DataFrame({
            'Clean_Name': bea_df.iloc[:, 1].astype(str).str.replace(r" \(Metropolitan Statistical Area\)", "", regex=True).str.strip(),
            'COL_VAL': pd.to_numeric(bea_df.iloc[:, -1], errors='coerce')
        }).dropna()
        filtered_by_type = pd.merge(filtered_by_type, bea_clean, left_on='AREA_TITLE', right_on='Clean_Name', how='left')
        if baseline_area in bea_clean['Clean_Name'].values:
            base_val = bea_clean[bea_clean['Clean_Name'] == baseline_area]['COL_VAL'].values[0]
            filtered_by_type['COL_INDEX'] = (filtered_by_type['COL_VAL'] / base_val) * 100
    except: pass

if 'COL_INDEX' not in filtered_by_type.columns:
    filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)

# --- RESULTS ---
final_df = filtered_by_type[filtered_by_type['AREA_TITLE'].isin(selected_areas)].copy()
if search_query:
    final_df = final_df[final_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

st.title("📊 Geographic Pay Banding Explorer")

if not final_df.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Market Wages (BLS)")
        st.plotly_chart(px.bar(final_df, x='AREA_TITLE', y='A_MEDIAN', color='A_MEDIAN', color_continuous_scale='Blues'), use_container_width=True)
    with c2:
        st.subheader("Cost of Living (Indexed)")
        color = '#9467bd' if col_source == "EPI (Family Budget)" else '#FFA500'
        st.plotly_chart(px.bar(final_df.drop_duplicates('AREA_TITLE'), x='AREA_TITLE', y='COL_INDEX', color_discrete_sequence=[color]), use_container_width=True)

    st.divider()
    st.subheader(f"🎯 Pay Differentials vs {baseline_area}")
    
    base_rows = final_df[final_df['AREA_TITLE'] == baseline_area]
    if not base_rows.empty:
        bw, bc = base_rows['A_MEDIAN'].mean(), base_rows['COL_INDEX'].mean()
        final_df['Market Gap %'] = ((final_df['A_MEDIAN'] - bw) / bw) * 100
        final_df['COL Gap %'] = ((final_df['COL_INDEX'] - bc) / bc) * 100
        final_df['Gap Variance'] = final_df['Market Gap %'] - final_df['COL Gap %']

        st.dataframe(final_df[['AREA_TITLE', 'OCC_TITLE', 'A_MEDIAN', 'Market Gap %', 'COL Gap %', 'Gap Variance']], 
                     column_config={"A_MEDIAN": st.column_config.NumberColumn("Market Wage", format="$%d"),
                                    "Market Gap %": st.column_config.NumberColumn("Market Gap", format="%+.1f%%"),
                                    "COL Gap %": st.column_config.NumberColumn("COL Gap", format="%+.1f%%"),
                                    "Gap Variance": st.column_config.NumberColumn("Variance", format="%+.1f%%")}, hide_index=True, use_container_width=True)

        # --- DYNAMIC STRATEGY INTERPRETER ---
        st.divider()
        st.subheader("💡 Strategic Recommendation")
        
        for index, row in final_df.iterrows():
            if row['AREA_TITLE'] == baseline_area:
                continue
            
            var = row['Gap Variance']
            city = row['AREA_TITLE']
            
            with st.expander(f"Analysis for {city}", expanded=True):
                if var > 5:
                    st.error(f"**Market Heat Detected (+{var:.1f}% Variance)**")
                    st.write(f"In {city}, market wages are rising much faster than the cost of living. To hire here, you must pay the full **{row['Market Gap %']:.1f}%** market premium, or you will lose talent to local competitors.")
                elif var < -5:
                    st.warning(f"**Cost of Living Squeeze Detected ({var:.1f}% Variance)**")
                    st.write(f"In {city}, the local market pays significantly less than the local cost of living suggests. **Recommendation:** Do not take the full market discount of {row['Market Gap %']:.1f}%. Instead, offer a smaller discount (closer to {row['COL Gap %']:.1f}%) to ensure the employee can afford to live there.")
                else:
                    st.success(f"**Efficient Alignment ({var:.1f}% Variance)**")
                    st.write(f"The market wages and cost of living in {city} are perfectly in sync relative to {baseline_area}. You can safely set your pay differential at **{row['Market Gap %']:.1f}%**.")
    else:
        st.warning("Please include the Baseline Area in your selection.")
else:
    st.info("Select regions and search for a job to begin.")
