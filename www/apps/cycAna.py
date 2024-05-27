import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import Kpro,getCsIndex,csIndexChart,getCsStock,d3plt,detailChart

def app():
    with st.form('form1'):
        with st.sidebar:
            cycCode = st.selectbox(
                '分析周期选项',
                ('3D','5D','21D','55D')
            )
            indexCode = getCsIndex.csIndexData(cycCode)
            indexCodeSel = st.selectbox(
                '指数选项',
                (indexCode['IndexName'])
            )
            submitted = st.form_submit_button('确认')
    if submitted:
        st_pyecharts(csIndexChart.Kchart(indexCodeSel),height='600px')
    
    with st.form('form2'):
        with st.sidebar:
            stockCode = getCsStock.getStock(indexCodeSel,cycCode)
            stockCodeSel = st.selectbox(
                '股票选项',
                (stockCode['code'])
        )
            submitted1 = st.form_submit_button('确认')
    if submitted1:
        tab1,tab2 = st.tabs(['Kpro','D3plt'])
        with tab1:
            # st.header('Kpro')         
            st_pyecharts(Kpro.Kchart(stockCodeSel),height='750px')
            st.header('财务分析')
            st_pyecharts(detailChart.line(stockCodeSel))
        with tab2:
            # st.header('D3plt')
            st.bokeh_chart(d3plt.d3(stockCodeSel),use_container_width=True)

            
