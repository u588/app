import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import getData,d3plt,Kpro,detailChart
from mootdx.quotes import Quotes
import re


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
            submitted2 = st.form_submit_button('确认')
        if submitted2:
            client = Quotes.factory(market='std')
            # a = client.F10C(symbol=stockCode)
            txt = client.F10(stockCodeSel, qf10)
            txt = txt.replace('│',' ')                
            txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符 
            tab1,tab2 ,tab3= st.tabs(['Kpro','D3plt','F10'])
            with tab1:
                # st.header('Kpro')         
                st_pyecharts(Kpro.Kchart(stockCodeSel),height='750px')
                st.header('财务分析')
                st_pyecharts(detailChart.line(stockCodeSel))
            with tab2:
                # st.header('D3plt')
                st.bokeh_chart(d3plt.d3(stockCodeSel),use_container_width=True)

            with tab3:
                st.subheader(qf10)
                st.text(txt)