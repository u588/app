import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import Kpro,indexChart,d3plt,detailChart

def app():
    with st.form('form1'):
        with st.sidebar:
            indexCode = st.text_input(label='指数查询',value='')
            submitted = st.form_submit_button('确认')
    if submitted:
        st_pyecharts(indexChart.Kchart(indexCode),height='600px')
    
    with st.form('form2'):
        with st.sidebar:
            stockCode = st.text_input(label='股票查询', value='')
            submitted1 = st.form_submit_button('确认')
    if submitted1:
        tab1,tab2 = st.tabs(['Kpro','D3plt'])
        with tab1:
            st_pyecharts(Kpro.Kchart(stockCode),height='750px')
            st.header('财务分析')
            st_pyecharts(detailChart.line(stockCode))
        with tab2:
            st.bokeh_chart(d3plt.d3(stockCode),use_container_width=True)

            
