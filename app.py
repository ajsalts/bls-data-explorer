import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page config
st.set_page_config(page_title="BLS Job Data Explorer", layout="wide")

# Built-in MERIC Cost of Living Index (State-Level, National Average = 100)
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
def load_data():
    df = pd.read_csv('cleaned_full_bls_data.csv') 
    
    area_mapping = {
        1: 'National (U.S.)', 2: 'State', 3: 'U.S. Territory', 
        4: 'Metropolitan Area (City/Region)', 6: 'Nonmetropolitan Area'
    }
    df['AREA_TYPE_LABEL'] = df['AREA_TYPE'].map(area_mapping)
    return df

df = load_data()

st.title("📊 Geo-Pay Banding & BLS Job Explorer")
st.markdown("Set a baseline city and calculate the exact percentage to adjust pay based on Local Market Rates or Cost of Living.")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Options")

area_types = df['AREA_TYPE_LABEL'].dropna().unique()
selected_area_type = st.sidebar.selectbox("Select Geographic Level", options=area_types, index=3)

filtered_by_type = df[df['AREA_TYPE_LABEL'] == selected_area_type]
all_areas = sorted(filtered_by_type['AREA_TITLE'].unique())

default_areas = []
if "Metropolitan" in selected_area_type:
    default_areas = [a for a in all_areas if "New York" in a or "San Francisco" in a or "Boulder" in a][:3]
elif "State" in selected_area_type:
    default_areas = ["California", "Colorado", "New York"]
if not default_areas and len(all_areas) > 0:
    default_areas = [all_areas[0]]

selected_areas = st.sidebar.multiselect("Select Specific Areas", all_areas, default=default_areas)
search_query = st.sidebar.text_input("Search Job Title (e.g., Data Scientist, Software)", "")

# --- ADVANCED PAY SCALE SETTINGS ---
st.sidebar.divider()
st.sidebar.subheader("Pay Scale Settings")
baseline_area = st.sidebar.selectbox("Select Baseline Area (0% Anchor)", options=selected_areas, 
                                     help="Choose the city you want to base your pay scale on.")

col_source = st.sidebar.radio("Select Cost of Living Data Source", options=[
    "MERIC (State-Level Built-in)",
    "BEA Regional Price Parities (City-Level)",
    "MIT Living Wage Calculator",
    "EPI Family Budget Calculator"
])

# --- LOGIC TO HANDLE COL SOURCES ---
missing_data_msg = None

if col_source == "MERIC (State-Level Built-in)":
    # Use the built-in dictionary
    filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)

elif col_source == "BEA Regional Price Parities (City-Level)":
    if os.path.exists("bea_data.csv"):
        # Logic to merge BEA data goes here once uploaded
        bea_df = pd.read_csv("bea_data.csv")
        # Placeholder merge logic:
        # filtered_by_type = pd.merge(filtered_by_type, bea_df, on='AREA_TITLE', how='left')
    else:
        filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)
        missing_data_msg = "**Missing BEA Data!** To use city-level Regional Price Parities, download the data from [BEA.gov](https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area), save it as `bea_data.csv`, and upload it to your GitHub repository. *(Falling back to MERIC state data for now).* "

elif col_source == "MIT Living Wage Calculator":
    if os.path.exists("mit_data.csv"):
        # Logic to merge MIT data goes here
        pass
    else:
        filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)
        missing_data_msg = "**Missing MIT Data!** The MIT Living Wage database requires you to request access on [their website](https://livingwage.mit.edu/). Once downloaded, save it as `mit_data.csv` and upload it. *(Falling back to MERIC state data for now).*"

elif col_source == "EPI Family Budget Calculator":
    if os.path.exists("epi_data.csv"):
        # Logic to merge EPI data goes here
        pass
    else:
        filtered_by_type['COL_INDEX'] = filtered_by_type['PRIM_STATE'].map(MERIC_COL_INDEX).fillna(100.0)
        missing_data_msg = "**Missing EPI Data!** Download the bulk data from the [EPI Website](https://www.epi.org/resources/budget/), save it as `epi_data.csv`, and upload it. *(Falling back to MERIC state data for now).*"

# --- UI NOTIFICATIONS ---
if missing_data_msg:
    st.info(missing_data_msg)

# Apply User Selections
filtered_df = filtered_by_type[filtered_by_type['AREA_TITLE'].isin(selected_areas)].copy()
if search_query:
    filtered_df = filtered_df[filtered_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

# --- MAIN DASHBOARD ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Raw Market Wage Comparison")
    if not filtered_df.empty:
        chart_data = filtered_df.groupby('AREA_TITLE')['A_MEDIAN'].mean().reset_index().sort_values('A_MEDIAN', ascending=False)
        fig = px.bar(chart_data, x='AREA_TITLE', y='A_MEDIAN', 
                     labels={'A_MEDIAN': 'Median Wage ($)', 'AREA_TITLE': 'Area'},
                     color='A_MEDIAN', color_continuous_scale='Viridis')
        fig.update_xaxes(tickangle=45, tickmode='array')
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Employment Distribution")
    if not filtered_df.empty:
        emp_chart = px.pie(filtered_df.nlargest(10, 'TOT_EMP'), values='TOT_EMP', names='OCC_TITLE',
                           title="Top Occupations by Employment")
        st.plotly_chart(emp_chart, use_container_width=True)

# --- DETAILED COMP PLANNER TABLE ---
st.subheader(f"HR Geo-Pay Scale Calculator")

if not filtered_df.empty and baseline_area:
    baseline_wages = filtered_df[filtered_df['AREA_TITLE'] == baseline_area].set_index('OCC_TITLE')['A_MEDIAN']
    filtered_df['Baseline_Raw_Wage'] = filtered_df['OCC_TITLE'].map(baseline_wages)
    
    baseline_col_df = filtered_df[filtered_df['AREA_TITLE'] == baseline_area]
    baseline_col = baseline_col_df['COL_INDEX'].iloc[0] if not baseline_col_df.empty else 100.0
    
    filtered_df['Market Pay Adjustment'] = ((filtered_df['A_MEDIAN'] - filtered_df['Baseline_Raw_Wage']) / filtered_df['Baseline_Raw_Wage']) * 100
    filtered_df['COL Equivalent Adjustment'] = ((filtered_df['COL_INDEX'] - baseline_col) / baseline_col) * 100

    display_cols = ['AREA_TITLE', 'OCC_TITLE', 'A_MEDIAN', 'COL_INDEX', 'Market Pay Adjustment', 'COL Equivalent Adjustment']
    
    st.dataframe(
        filtered_df[display_cols],
        column_config={
            "A_MEDIAN": st.column_config.NumberColumn("Local Market Wage", format="$%d"),
            "COL_INDEX": st.column_config.NumberColumn("Local COL Index", format="%.1f"),
            "Market Pay Adjustment": st.column_config.NumberColumn(
                "Market Rate vs Baseline",
                help=f"How much less/more LOCAL EMPLOYERS actually pay compared to {baseline_area}.",
                format="%+.1f%%", 
            ),
            "COL Equivalent Adjustment": st.column_config.NumberColumn(
                "COL vs Baseline",
                help=f"How much cheaper/more expensive it is to LIVE there compared to {baseline_area}.",
                format="%+.1f%%", 
            ),
        },
        hide_index=True,
        use_container_width=True
    )
