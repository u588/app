import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import Kpro,indexChart,d3plt,detailChart,gganChart,gganPx,fenX
from mootdx.quotes import Quotes
import pandas as pd
import re
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxFS')

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
                            ('最新提示',
                            '公司概况',
                            '财务分析',
                            '股本结构',
                            '股东研究',
                            '机构持股',
                            '分红融资',
                            '高管治理',                                
                            '资金动向',
                            '资本运作',
                            '热点题材',
                            '公司公告',
                            '公司报道',
                            '经营分析',
                            '行业分析',
                            '价值分析',)
                        )            
            submitted1 = st.form_submit_button('确认')
    if submitted1:
        client = Quotes.factory(market='std')
        # a = client.F10C(symbol=stockCode)
        txt = client.F10(stockCode, qf10)
        try:
            txt = txt[:txt.find('〖免责条款〗')]
        except:
            pass
        txt = txt.replace('│',' ')                
        txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符         

        tab1,tab2 ,tab3= st.tabs(['Kpro','D3plt','F10'])
        with tab1:
            st_pyecharts(Kpro.Kchart(stockCode),height='750px')
            # st.bokeh_chart(BokK.K(stockCode))
            st.header('财务分析')
            st_pyecharts(detailChart.line(stockCode))
        with tab2:
            st.bokeh_chart(d3plt.d3(stockCode),use_container_width=True)
        with tab3:
            st.subheader(qf10)
            st.text(txt)
            # st.markdown(txt)

    with st.form('form3'):
        FSCode = pd.read_sql('FSCode',eng)
        eng.dispose()
        anData = FSCode[['L1Code','L1Name']].drop_duplicates().reset_index(drop=True).loc[1:13].reset_index(drop=True)
        with st.sidebar:
            anName = st.selectbox(
                '专业财务信息',
                (list(anData['L1Name']))
            )   
            submitted = st.form_submit_button('确认')

    if submitted:
        tab1,tab2,tab3 = st.tabs(['历史数据Line','历史数据Bar','3'], )
        with tab1:
            st_pyecharts(gganChart.gChart(stockCode,list(anData[anData['L1Name']==anName]['L1Code'])[0]),height='600px')
        with tab2:        
            gganPx.ggPx(stockCode,list(anData[anData['L1Name']==anName]['L1Code'])[0])


    with st.form('form4'):
        # FSCode = pd.read_sql('FSCode',eng)
        # eng.dispose()
        # anData = FSCode[['L1Code','L1Name']].drop_duplicates().reset_index(drop=True).loc[1:13].reset_index(drop=True)
        with st.sidebar:
            fenCode = st.selectbox(
                '聚类分析',
                ('每股指标','股本股东','发展能力分析','偿债能力分析','获利能力分析','经营能力分析','现金流分析','资本结构分析')
            )   
            submitted = st.form_submit_button('确认')
        if submitted:
            fenX.fenChart(stockCode, list(anData[anData['L1Name']==fenCode]['L1Code'])[0])