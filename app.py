import streamlit as st
import pandas as pd
import plotly.express as px

# Set page config
st.set_page_config(page_title="BLS Job Data Explorer", layout="wide")

# Cost of Living Index by State (Approximate 2024 data, National Average = 100)
COL_INDEX = {
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

# Load the data
@st.cache_data
def load_data():
    # IMPORTANT: Ensure this filename matches EXACTLY what is in your GitHub repo!
    df = pd.read_csv('cleaned_full_bls_data.csv') 
    
    # Map area types
    area_mapping = {
        1: 'National (U.S.)', 2: 'State', 3: 'U.S. Territory', 
        4: 'Metropolitan Area (City/Region)', 6: 'Nonmetropolitan Area'
    }
    df['AREA_TYPE_LABEL'] = df['AREA_TYPE'].map(area_mapping)
    
    # Add COL Index based on the primary state (PRIM_STATE)
    df['COL_INDEX'] = df['PRIM_STATE'].map(COL_INDEX).fillna(100.0)
    
    # Calculate Adjusted Wages
    df['ADJ_A_MEDIAN'] = df['A_MEDIAN'] / (df['COL_INDEX'] / 100)
    
    return df

df = load_data()

st.title("📊 Comprehensive BLS Job Explorer (May 2025)")
st.markdown("Search, compare, and analyze employment and wage data. **Includes Cost of Living (COL) Adjustments!**")

# Sidebar Filters
st.sidebar.header("Filter Options")

area_types = df['AREA_TYPE_LABEL'].dropna().unique()
selected_area_type = st.sidebar.selectbox("Select Geographic Level", options=area_types, index=3)

filtered_by_type = df[df['AREA_TYPE_LABEL'] == selected_area_type]
all_areas = sorted(filtered_by_type['AREA_TITLE'].unique())

default_areas = []
if "Metropolitan" in selected_area_type:
    default_areas = [a for a in all_areas if "New York" in a or "Los Angeles" in a][:2]
elif "State" in selected_area_type:
    default_areas = ["California", "Texas", "New York"]

if not default_areas and len(all_areas) > 0:
    default_areas = [all_areas[0]]

selected_areas = st.sidebar.multiselect("Select Specific Areas", all_areas, default=default_areas)
search_query = st.sidebar.text_input("Search Job Title (e.g., Software, Nurse, Manager)", "")

# COL Toggle
st.sidebar.divider()
st.sidebar.subheader("Advanced Settings")
use_col = st.sidebar.toggle("Adjust for Cost of Living", value=False, 
                            help="Recalculates wages based on the state's cost of living. (National Avg = 100)")

# Apply Filters
filtered_df = filtered_by_type[filtered_by_type['AREA_TITLE'].isin(selected_areas)]
if search_query:
    filtered_df = filtered_df[filtered_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

# Set the wage column to use based on the user's toggle choice
wage_col = 'ADJ_A_MEDIAN