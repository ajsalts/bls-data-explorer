import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re

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

# --- APP LAYOUT ---
st.title("📊 Geo-Pay Banding & Compensation Planner")
st.markdown("Compare raw market wages against local cost of living to determine geographic pay differentials.")

# --- SIDEBAR ---
st.sidebar.header("1. Filter Locations")
area_types = df_bls['AREA_TYPE_LABEL'].dropna().unique()
selected_area_type = st.sidebar.selectbox("Geographic Level", options=area_types, index=3)

filtered_by_type = df_bls[df_bls['AREA_TYPE_LABEL'] == selected_area_type].copy()
all_areas = sorted(filtered_by_type['AREA_TITLE'].unique())

# Set intelligent defaults
default_areas = []
if "Metropolitan" in selected_area_type:
    default_areas = [a for a in all_areas if "San Francisco" in a or "Boulder" in a or "New York" in a][:3]
elif "State" in selected_area_type:
    default_areas = ["California", "Colorado", "Texas"]

selected_areas = st.sidebar.multiselect("Select Specific Areas", all_areas, default=default_areas)
search_query = st.sidebar.text_input("Job Title Search", "Data Scientist")

st.sidebar.divider()
st.sidebar.header("2. Comp Planning Settings")

baseline_area = st.sidebar.selectbox(
    "Select Baseline Area (0% Anchor)", 
    options=selected_areas if selected_areas else all_areas,
    help="This is your company's primary location or your 100% pay benchmark."
)

col_source = st.sidebar.radio("Cost of Living Data Source", options=[
    "MERIC (State-Level)",
    "BEA (City-Level CSV)",
    "MIT/EPI (Manual CSV Upload)"
])

# --- COL LOGIC ---
missing_data_msg = None

if col_source == "BEA (City-Level CSV)":
    if os.path.exists("bea_data.csv"):
        try:
            bea_df = pd.read_csv("bea_data.csv")
            name_col = 'GeoName' if 'GeoName' in bea_df.columns else bea_df.columns[1]
            
            # Cleaning the BEA GeoNames to match BLS titles
            # Removes " (Metropolitan Statistical Area)" and trailing spaces
            bea_df['Cleaned_Area'] = bea_df[name_col].astype(str).str.replace(r" \(Metropolitan Statistical Area\)", "", regex=True).str.strip()
            
            # Grab the last column (most recent year) as the index
            val_col = bea_df.columns[-1]
            bea_subset = bea_df[['Cleaned_Area', val_col]].rename(columns={val_col: 'COL_INDEX'})
            bea_subset['COL_INDEX'] = pd.to_numeric(bea_subset['COL_INDEX'], errors='coerce')
            
            # Merge with BLS data
            filtered_by_type = pd.merge(filtered_by_type, bea_subset, left_on='AREA_TITLE', right_on='Cleaned_Area', how='left')
            filtered_by_type['COL_INDEX'] = filtered_by_type['COL_INDEX'].fillna(100.0)
        except Exception as e:
            st.error(f"Error merging BEA data: {e}")
            filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)
    else:
        missing_data_msg = "BEA file not found. Upload `bea_data.csv` to GitHub. Using State-level fallback."
        filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)

else:
    # Use State-level MERIC data
    filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)

if missing_data_msg:
    st.info(missing_data_msg)

# --- FILTER DATA ---
final_df = filtered_by_type[filtered_by_type['AREA_TITLE'].isin(selected_areas)].copy()
if search_query:
    final_df = final_df[final_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

# --- VISUALIZATIONS ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("Market Wage Gap")
    if not final_df.empty:
        fig_wage = px.bar(final_df, x='AREA_TITLE', y='A_MEDIAN', color='A_MEDIAN', 
                         labels={'A_MEDIAN':'Annual Median Wage', 'AREA_TITLE':''},
                         color_continuous_scale='Blues')
        st.plotly_chart(fig_wage, use_container_width=True)

with c2:
    st.subheader("Cost of Living Index")
    if not final_df.empty:
        fig_col = px.bar(final_df.drop_duplicates('AREA_TITLE'), x='AREA_TITLE', y='COL_INDEX', 
                        labels={'COL_INDEX':'Index (100 = Nat. Avg)', 'AREA_TITLE':''},
                        color_discrete_sequence=['#FFA500'])
        st.plotly_chart(fig_col, use_container_width=True)

# --- THE CALCULATOR ---
st.divider()
st.subheader("🎯 Geographic Pay Differentials")

if not final_df.empty and baseline_area:
    # Calculate Baseline Values
    # We use .mean() just in case the search query returns multiple job levels
    base_wage = final_df[final_df['AREA_TITLE'] == baseline_area]['A_MEDIAN'].mean()
    base_col = final_df[final_df['AREA_TITLE'] == baseline_area]['COL_INDEX'].mean()

    if base_wage > 0:
        # 1. Market Rate Adjustment: How much less do employers in City X pay compared to Baseline?
        final_df['Market_Adjustment'] = ((final_df['A_MEDIAN'] - base_wage) / base_wage) * 100
        
        # 2. COL Adjustment: How much cheaper is it to live in City X compared to Baseline?
        final_df['COL_Adjustment'] = ((final_df['COL_INDEX'] - base_col) / base_col) * 100

        display_df = final_df[['AREA_TITLE', 'OCC_TITLE', 'A_MEDIAN', 'COL_INDEX', 'Market_Adjustment', 'COL_Adjustment']]

        st.dataframe(
            display_df,
            column_config={
                "AREA_TITLE": "Region",
                "OCC_TITLE": "Job Title",
                "A_MEDIAN": st.column_config.NumberColumn("Local Wage", format="$%d"),
                "COL_INDEX": st.column_config.NumberColumn("COL Index", format="%.1f"),
                "Market_Adjustment": st.column_config.NumberColumn(
                    f"Market Gap vs {baseline_area}",
                    help="The raw percentage difference in market wages.",
                    format="%+.1f%%"
                ),
                "COL_Adjustment": st.column_config.NumberColumn(
                    f"COL Gap vs {baseline_area}",
                    help="The percentage difference in cost of living.",
                    format="%+.1f%%"
                )
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning(f"No wage data found for {baseline_area} with the current job search.")
else:
    st.info("Select regions and search for a job title to generate the pay scale calculator.")
