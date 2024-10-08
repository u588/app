import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import getData,d3plt,Kpro,detailChart
from mootdx.quotes import Quotes
import re
import pandas as pd
import plotly.express as px


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
            # qf10 = st.selectbox(
            #                 'F10信息',
            #                 ('最新提示',
            #                 '公司概况',
            #                 '财务分析',
            #                 '股本结构',
            #                 '股东研究',
            #                 '机构持股',
            #                 '分红融资',
            #                 '高管治理',                                
            #                 '资金动向',
            #                 '资本运作',
            #                 '热点题材',
            #                 '公司公告',
            #                 '公司报道',
            #                 '经营分析',
            #                 '行业分析',
            #                 '价值分析',)
            #             ) 
            submitted = st.form_submit_button('确认')
        if submitted:
            # client = Quotes.factory(market='std')
            # # a = client.F10C(symbol=stockCode)
            # txt = client.F10(stockCodeSel, qf10)
            # try:
            #     txt = txt[:txt.find('〖免责条款〗')]
            # except:
            #     pass
            # txt = txt.replace('│',' ')                
            # txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符 
            tab1,tab2 = st.tabs(['Kpro','D3plt'])
            with tab1:
                # st.header('Kpro')         
                st_pyecharts(Kpro.Kchart(stockCodeSel),height='750px')
                # st.header('财务分析')
                # st_pyecharts(detailChart.line(stockCodeSel))
            with tab2:
                # st.header('D3plt')
                st.bokeh_chart(d3plt.d3(stockCodeSel),use_container_width=True)

            # with tab3:
            #     st.subheader(qf10)
            #     st.text(txt)

    with st.form('form1'):    
        with st.sidebar:
            anCode = st.selectbox(
                '行业分析',
                (["市场表现排名","公司规模排名","估值水平排名","财务状况排名"])
            )
            submitted1 = st.form_submit_button('确认')
        if submitted1:
            client = Quotes.factory(market='std')
            txt = client.F10(stockCodeSel, '行业分析')[116:]
            txt = txt.replace('│',' ')                
            txt = re.sub('([\u2500-\u25f7])','',txt)

            def getFind(anCode):
                match anCode:
                    case "市场表现排名":
                        lsCode = ['【2.市场表现排名】','【3.公司规模排名】',["股票名称", "一周涨跌幅%","一月涨跌幅%","三月涨跌幅%","半年涨跌幅%","一年涨跌幅%"]]
                        return(lsCode)
                    case "公司规模排名":
                        lsCode = ['【3.公司规模排名】','【4.估值水平排名】',["股票名称","A股总市值(亿)","A股流通市值(亿)","实际流通A股(亿)","总股本(亿)","股价(元)"]]
                        return(lsCode)
                    case "估值水平排名":
                        lsCode = ['【4.估值水平排名】','【5.财务状况排名】',['股票名称','市盈率(TTM)','市盈率(LYR)','市净率(MRQ)','市销率(TTM)','市现率(TTM)']]
                        return(lsCode)
                    case "财务状况排名":
                        lsCode = ['【5.财务状况排名】','EOF',["股票名称","每股收益(元)","每股净资产(元)","每股现金流(元)","销售净利率%","净利润增长率%"]]
                        return(lsCode)

            lsCode =  getFind(anCode)

            fi = txt[txt.find(lsCode[0]):]
            ff = fi[:fi.find(lsCode[1])]
            dd = ff.replace('─','').splitlines(keepends=False)
            Data = pd.DataFrame(columns=lsCode[2])
            i = 3
            while i < len(dd):
                lis = re.split(r"\s+", dd[i])[-6:]
                if len(lis)!=6:
                    i = i+1
                    # pass
                else:
                    df = pd.DataFrame(lis).T
                    df.columns=lsCode[2]
                    Data = pd.concat([Data, df],axis=0)
                    i=i+1
            Data.reset_index(drop=True,inplace=True)
            Data = Data.replace('---',0)

            def to_numeric_safe(value):
                try:
                    return pd.to_numeric(value)
                except (ValueError, TypeError):
                    return value

            ddf  = Data.map(to_numeric_safe)


            fig = px.bar(ddf, y=ddf.columns[0], x=ddf.columns[1:], title=anCode,
                        barmode='relative', hover_name=ddf.columns[0],text_auto='')
            # fig.update_layout(dragmode='pan',legend_itemclick='toggleothers',)
            fig.update_layout(dragmode='pan',)


            tab3, tab4 = st.tabs(['3','4'])
            with tab3:
                stta = ddf.style.background_gradient(cmap='Blues')
                stta = stta.format('{:,.2f}', subset=list(ddf.columns[1:]))    
                st.dataframe(stta, hide_index=True)
            with tab4:
                st.plotly_chart(fig,config={'scrollZoom':True})