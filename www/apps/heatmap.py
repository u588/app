import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import getData,d3plt,Kpro,detailChart

def app():
    with st.form('form'):    
        with st.sidebar:
            selDate = getData.getDate()
            dateSel = st.selectbox(
                '选择日期',
                (selDate['datetime'])
            )
            selCode = getData.getCode(dateSel)
            stockCodeSel = st.selectbox(
                '选择股票',
                (selCode['code'])
            )
            submitted2 = st.form_submit_button('确认')
        if submitted2:
            tab1,tab2 = st.tabs(['Kpro','D3plt'])
            with tab1:
                # st.header('Kpro')         
                st_pyecharts(Kpro.Kchart(stockCodeSel),height='750px')
                st.header('财务分析')
                st_pyecharts(detailChart.line(stockCodeSel))
            with tab2:
                # st.header('D3plt')
                st.bokeh_chart(d3plt.d3(stockCodeSel),use_container_width=True)