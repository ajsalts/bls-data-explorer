import streamlit as st
import pandas as pd
import plotly.express as px

# Set page config
st.set_page_config(page_title="BLS Job Data Explorer", layout="wide")

# Load the data
@st.cache_data
def load_data():
    # Read the new full cleaned dataset
    df = pd.read_csv('cleaned_full_bls_data.csv')
    
    # Map area types to human-readable labels
    area_mapping = {
        1: 'National (U.S.)',
        2: 'State',
        3: 'U.S. Territory',
        4: 'Metropolitan Area (City/Region)',
        6: 'Nonmetropolitan Area'
    }
    df['AREA_TYPE_LABEL'] = df['AREA_TYPE'].map(area_mapping)
    return df

df = load_data()

st.title("📊 Comprehensive BLS Job Explorer (May 2025)")
st.markdown("Search, compare, and analyze employment and wage data across U.S. States, Cities, and Regions.")

# Sidebar Filters
st.sidebar.header("Filter Options")

# 1. Filter by Area Type first
area_types = df['AREA_TYPE_LABEL'].dropna().unique()
selected_area_type = st.sidebar.selectbox("Select Geographic Level", options=area_types, index=3) # Default to City/Region

# 2. Filter available areas based on the selected type
filtered_by_type = df[df['AREA_TYPE_LABEL'] == selected_area_type]
all_areas = sorted(filtered_by_type['AREA_TITLE'].unique())

# Set some smart defaults if available
default_areas = []
if "Metropolitan Area (City/Region)" in selected_area_type:
    default_areas = [a for a in all_areas if "New York" in a or "Los Angeles" in a][:2]
elif "State" in selected_area_type:
    default_areas = ["California", "Texas", "New York"]

if not default_areas and len(all_areas) > 0:
    default_areas = [all_areas[0]]

selected_areas = st.sidebar.multiselect("Select Specific Areas", all_areas, default=default_areas)

# 3. Search by Job Title
search_query = st.sidebar.text_input("Search Job Title (e.g., Software, Nurse, Manager)", "")

# Apply Filters
filtered_df = filtered_by_type[filtered_by_type['AREA_TITLE'].isin(selected_areas)]
if search_query:
    filtered_df = filtered_df[filtered_df['OCC_TITLE'].str.contains(search_query, case=False, na=False)]

# Main Dashboard
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Wage Comparison (Annual Median)")
    if not filtered_df.empty:
        # Group by area for the comparison chart
        chart_data = filtered_df.groupby('AREA_TITLE')['A_MEDIAN'].mean().reset_index().sort_values('A_MEDIAN', ascending=False)
        fig = px.bar(chart_data, x='AREA_TITLE', y='A_MEDIAN', 
                     labels={'A_MEDIAN': 'Median Annual Wage ($)', 'AREA_TITLE': 'Area'},
                     color='A_MEDIAN', color_continuous_scale='Viridis')
        # Truncate long x-axis labels for cities
        fig.update_xaxes(tickangle=45, tickmode='array') 
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please select areas or search for a job to see comparisons.")

with col2:
    st.subheader("Employment Distribution")
    if not filtered_df.empty:
        emp_chart = px.pie(filtered_df.nlargest(10, 'TOT_EMP'), values='TOT_EMP', names='OCC_TITLE',
                           title=f"Top 10 Occupations by Employment")
        st.plotly_chart(emp_chart, use_container_width=True)

# Detailed Table
st.subheader("Detailed Job Data")
display_cols = ['AREA_TITLE', 'OCC_TITLE', 'TOT_EMP', 'H_MEDIAN', 'A_MEDIAN']
st.dataframe(filtered_df[display_cols], use_container_width=True)

# Deep Dive for a specific job across ALL areas of the selected type
if search_query:
    st.divider()
    st.subheader(f"National Deep Dive: {search_query} ({selected_area_type})")
    
    # Filter the entire dataset for this job and area type (ignoring the specific user-selected cities)
    compare_df = filtered_by_type[filtered_by_type['OCC_TITLE'].str.contains(search_query, case=False, na=False)]
    
    if not compare_df.empty:
        # Show top 10 highest paying areas for this specific job
        top_areas = compare_df.sort_values('A_MEDIAN', ascending=False).head(10)
        fig_top = px.bar(top_areas, x='A_MEDIAN', y='AREA_TITLE', orientation='h',
                         title=f"Highest Paying Areas for '{search_query}'",
                         labels={'A_MEDIAN': 'Median Annual Wage ($)', 'AREA_TITLE': 'Area'},
                         color='A_MEDIAN', color_continuous_scale='Plasma')
        fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True)