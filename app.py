import streamlit as st
import pandas as pd
import plotly.express as px

# Set page config
st.set_page_config(page_title="BLS Job Data Explorer", layout="wide")

# Cost of Living Index by State (Approximate 2024 data, National Average = 100)
# Sources: MERIC / C2ER Cost of Living Index
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
    df = pd.read_csv('cleaned_full_bls_data.zip') # Ensure you are using the zip file from earlier!
    
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

# Area Type Filter
area_types = df['AREA_TYPE_LABEL'].dropna().unique()
selected_area_type = st.sidebar.selectbox("Select Geographic Level", options=area_types, index=3)

# Area Selection Filter
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

# Job Search Filter
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
wage_col = 'ADJ_A_MEDIAN' if use_col else 'A_MEDIAN'
wage_label = 'COL-Adjusted Median Annual Wage ($)' if use_col else 'Raw Median Annual Wage ($)'

# Main Dashboard
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Wage Comparison")
    if not filtered_df.empty:
        chart_data = filtered_df.groupby('AREA_TITLE')[wage_col].mean().reset_index().sort_values(wage_col, ascending=False)
        fig = px.bar(chart_data, x='AREA_TITLE', y=wage_col, 
                     labels={wage_col: wage_label, 'AREA_TITLE': 'Area'},
                     color=wage_col, color_continuous_scale='Viridis')
        fig.update_xaxes(tickangle=45, tickmode='array')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please select areas or search for a job to see comparisons.")

with col2:
    st.subheader("Employment Distribution")
    if not filtered_df.empty:
        emp_chart = px.pie(filtered_df.nlargest(10, 'TOT_EMP'), values='TOT_EMP', names='OCC_TITLE',
                           title="Top Occupations by Employment")
        st.plotly_chart(emp_chart, use_container_width=True)

# Detailed Table
st.subheader("Detailed Job Data")
display_cols = ['AREA_TITLE', 'OCC_TITLE', 'TOT_EMP', 'A_MEDIAN', 'COL_INDEX', 'ADJ_A_MEDIAN']
st.dataframe(filtered_df[display_cols].style.format({
    'A_MEDIAN': '${:,.0f}',
    'ADJ_A_MEDIAN': '${:,.0f}',
    'COL_INDEX': '{:.1f}'
}), use_container_width=True)

# Deep Dive Comparison
if search_query:
    st.divider()
    st.subheader(f"National Deep Dive: {search_query} ({selected_area_type})")
    
    compare_df = filtered_by_type[filtered_by_type['OCC_TITLE'].str.contains(search_query, case=False, na=False)]
    
    if not compare_df.empty:
        # Show top 10 highest paying areas based on selected wage type
        top_areas = compare_df.sort_values(wage_col, ascending=False).head(10)
        
        # Create a side-by-side grouped bar chart to show both Raw and Adjusted wages
        melted_df = top_areas.melt(id_vars=['AREA_TITLE'], value_vars=['A_MEDIAN', 'ADJ_A_MEDIAN'], 
                                   var_name='Wage Type', value_name='Amount')
        melted_df['Wage Type'] = melted_df['Wage Type'].map({'A_MEDIAN': 'Raw Wage', 'ADJ_A_MEDIAN': 'Real (COL Adjusted) Wage'})
        
        fig_top = px.bar(melted_df, x='Amount', y='AREA_TITLE', color='Wage Type', orientation='h', barmode='group',
                         title=f"Top 10 Paying Areas for '{search_query}' (Raw vs. Real Wage)",
                         labels={'Amount': 'Annual Wage ($)', 'AREA_TITLE': 'Area'})
        fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True)