import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def render_health_score_gauge(score: int):
    """
    Renders a gauge chart representing the Financial Cash Flow Health Score.
    """
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Financial Health Score", 'font': {'size': 20, 'color': '#1A365D'}},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#4A5568"},
            'bar': {'color': "#1F4E79"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "#CBD5E0",
            'steps': [
                {'range': [0, 40], 'color': '#FEB2B2'},      # Poor (Red)
                {'range': [40, 70], 'color': '#FEEBC8'},     # Average (Orange)
                {'range': [70, 90], 'color': '#C6F6D5'},     # Good (Light Green)
                {'range': [90, 100], 'color': '#9AE6B4'}     # Excellent (Green)
            ],
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        height=250
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_debit_credit_trend(df: pd.DataFrame):
    """
    Renders daily debit vs credit grouped bar or line chart.
    """
    # Group by Date
    daily = df.groupby('date')[['debit', 'credit']].sum().reset_index()
    
    fig = px.bar(
        daily, 
        x='date', 
        y=['debit', 'credit'],
        barmode='group',
        labels={'value': 'Amount (₹)', 'variable': 'Type'},
        title='Debit vs Credit Trends',
        color_discrete_map={'debit': '#E53E3E', 'credit': '#3182CE'}
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title="Date",
        yaxis_title="Amount (₹)",
        margin=dict(l=20, r=20, t=45, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_category_donut(df: pd.DataFrame):
    """
    Renders Donut chart showing category breakdown.
    """
    cat_df = df.groupby('category').size().reset_index(name='count')
    
    fig = px.pie(
        cat_df, 
        values='count', 
        names='category', 
        hole=0.4,
        title='Category Distribution',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=45, b=20),
        height=320
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_nature_pie(df: pd.DataFrame):
    """
    Renders Nature (payment mode) Pie chart.
    """
    nat_df = df.groupby('nature').size().reset_index(name='count')
    
    fig = px.pie(
        nat_df, 
        values='count', 
        names='nature',
        title='Nature (Payment Mode) Distribution',
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=45, b=20),
        height=320
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_top_expense_categories(df: pd.DataFrame):
    """
    Renders Horizontal Bar Chart showing Top 10 categories with debit amounts.
    """
    expense_df = df[df['debit'] > 0]
    top_cat = expense_df.groupby('category')['debit'].sum().reset_index()
    top_cat = top_cat.sort_values(by='debit', ascending=False).head(10)
    
    fig = px.bar(
        top_cat,
        y='category',
        x='debit',
        orientation='h',
        title='Top 10 Expense Categories',
        labels={'debit': 'Total Debit (₹)', 'category': 'Category'},
        color_discrete_sequence=['#E53E3E']
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title="Amount (₹)",
        yaxis_title="Category",
        margin=dict(l=20, r=20, t=45, b=20),
        height=320
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_confidence_distribution(df: pd.DataFrame):
    """
    Renders Histogram representing classification confidence score.
    """
    fig = px.histogram(
        df,
        x='confidence',
        nbins=20,
        title='AI Classification Confidence Distribution',
        labels={'confidence': 'Confidence Score (%)'},
        color_discrete_sequence=['#319795']
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title="Confidence (%)",
        yaxis_title="Transaction Count",
        margin=dict(l=20, r=20, t=45, b=20),
        height=320
    )
    
    st.plotly_chart(fig, use_container_width=True)
