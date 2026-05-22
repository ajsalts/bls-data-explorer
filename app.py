import streamlit as st
import pandas as pd
import plotly.express as px

# Set page config
st.set_page_config(page_title="BLS Job Data Explorer", layout="wide")

# Load the data
@st.cache_data
def load_data():
    df = pd.read_csv('cleaned_bls_data.csv')
    return df

df = load_data()

st.title("📊 Bureau of Labor Statistics Explorer (May 2025)")
st.markdown("Search, compare, and analyze employment and wage data across the US.")

# Sidebar Filters
st.sidebar.header("Filter Options")
all_states = sorted(df['AREA_TITLE'].unique())
selected_states = st.sidebar.multiselect("Select States/Areas", all_states, default=["Alabama", "California", "New York"])

# Search by Job Title
search_query = st.sidebar.text_input("Search Job Title", "")

# Filter data
filtered_df = df[df['AREA_TITLE'].isin(selected_states)]
if search_query:
    filtered_df = filtered_df[filtered_df['OCC_TITLE'].str.contains(search_query, case=False)]

# Main Dashboard
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Wage Comparison (Annual Median)")
    if not filtered_df.empty:
        # Group by state for the comparison chart
        chart_data = filtered_df.groupby('AREA_TITLE')['A_MEDIAN'].mean().reset_index().sort_values('A_MEDIAN', ascending=False)
        fig = px.bar(chart_data, x='AREA_TITLE', y='A_MEDIAN', 
                     labels={'A_MEDIAN': 'Median Annual Wage ($)', 'AREA_TITLE': 'State'},
                     color='A_MEDIAN', color_continuous_scale='Viridis')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please select states or search for a job to see comparisons.")

with col2:
    st.subheader("Employment Distribution")
    if not filtered_df.empty:
        emp_chart = px.pie(filtered_df.nlargest(10, 'TOT_EMP'), values='TOT_EMP', names='OCC_TITLE',
                           title="Top 10 Occupations by Employment in Selected Areas")
        st.plotly_chart(emp_chart, use_container_width=True)

# Detailed Table
st.subheader("Detailed Job Data")
st.dataframe(filtered_df[['AREA_TITLE', 'OCC_TITLE', 'TOT_EMP', 'H_MEDIAN', 'A_MEDIAN']], use_container_width=True)

# Comparison Logic
if search_query:
    st.divider()
    st.subheader(f"Deep Dive: {search_query}")
    compare_df = df[df['OCC_TITLE'].str.contains(search_query, case=False)]
    
    # Show top 5 states for this specific job
    top_states = compare_df.sort_values('A_MEDIAN', ascending=False).head(10)
    fig_top = px.bar(top_states, x='A_MEDIAN', y='AREA_TITLE', orientation='h',
                     title=f"Highest Paying States for {search_query}",
                     labels={'A_MEDIAN': 'Median Annual Wage ($)', 'AREA_TITLE': 'State'})
    st.plotly_chart(fig_top, use_container_width=True)