import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import Kpro,getCsIndex,csIndexChart,getCsStock,d3plt,gganChart,gganPx,fenX
from mootdx.quotes import Quotes
import pandas as pd
import re
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56:5432/tdxFS')


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
                (stockCode['code']+' : '+stockCode['StockName'])
        )
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
                            '研报评级',)
                        ) 
            submitted1 = st.form_submit_button('确认')
    if submitted1:
        client = Quotes.factory(market='std')
        # a = client.F10C(symbol=stockCode)
        txt = client.F10(stockCodeSel, qf10)
        try:
            txt = txt[:txt.find('〖免责条款〗')]
        except:
            pass
        txt = txt.replace('│',' ')                
        txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符 
        tab1,tab2,tab3 = st.tabs(['Kpro','D3plt','F10'])
        with tab1:
            # st.header('Kpro')         
            st_pyecharts(Kpro.Kchart(stockCodeSel[:6]),renderer='canvas',height='750px',key='k')
            # st.header('财务分析')
            # st_pyecharts(detailChart.line(stockCodeSel[:6]),renderer="canvas",key='f')

        with tab2:
            # st.header('D3plt')
            # st.bokeh_chart(d3plt.d3(stockCodeSel[:6]),use_container_width=True)
            st.bokeh_chart(d3plt.d3(stockCodeSel[:6]),width='stretch')
        

        with tab3:
            st.subheader(qf10)
            st.text(txt)

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
            st_pyecharts(gganChart.gChart(stockCodeSel[:6],list(anData[anData['L1Name']==anName]['L1Code'])[0]),height='600px')
        with tab2:        
            gganPx.ggPx(stockCodeSel[:6],list(anData[anData['L1Name']==anName]['L1Code'])[0])


    with st.form('form4'):
        # FSCode = pd.read_sql('FSCode',eng)
        # eng.dispose()
        # anData = FSCode[['L1Code','L1Name']].drop_duplicates().reset_index(drop=True).loc[1:13].reset_index(drop=True)
        with st.sidebar:
            fenCode = st.selectbox(
                '聚类分析',
                ('发展能力分析','偿债能力分析','获利能力分析','经营能力分析','现金流分析','资本结构分析')
            )   
            submitted = st.form_submit_button('确认')
        if submitted:
            fenX.fenChart(stockCodeSel[:6], list(anData[anData['L1Name']==fenCode]['L1Code'])[0])