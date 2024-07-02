import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import Kpro,indexChart,d3plt,detailChart,BokK
from mootdx.quotes import Quotes
import re


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
            qf10 = st.selectbox(
                            'F10信息',
                            ('最新提示','公司概况')
                        )            
            submitted1 = st.form_submit_button('确认')
    if submitted1:
        tab1,tab2 ,tab3= st.tabs(['Kpro','D3plt','F10'])
        with tab1:
            st_pyecharts(Kpro.Kchart(stockCode),height='750px')
            # st.bokeh_chart(BokK.K(stockCode))
            st.header('财务分析')
            st_pyecharts(detailChart.line(stockCode))
        with tab2:
            st.bokeh_chart(d3plt.d3(stockCode),use_container_width=True)
        with tab3:
            client = Quotes.factory(market='std')
            # a = client.F10C(symbol=stockCode)
            txt = client.F10(stockCode, qf10)
            txt = txt.replace('│',' ')                
            txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符 

            st.subheader(qf10)
            st.text(txt)