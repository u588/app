import streamlit as st
from streamlit_echarts import st_pyecharts
# from chart import getData,d3plt,Kpro,detailChart
from chart import getData,Kpro
from mootdx.quotes import Quotes
import numpy as np 
import re
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

from pytdx.hq import TdxHq_API
api = TdxHq_API()

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxStocks')

StockList = pd.read_sql('StocksList', eng)[['code','name']]
StockList.columns=['股票编码','股票名称']

def norm(df, column_name, n):
    min_val = df[column_name].min()
    max_val = df[column_name].max()
    normalized_column = (df[column_name] - min_val) / (max_val - min_val)
    scaled_column = normalized_column * (n - 1) + 1
    discrete_scaled_column = scaled_column.round().astype(int)
    return discrete_scaled_column


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
            submitted = st.form_submit_button('选择确认')
            
            anCode = st.selectbox(
                '行业分析',
                (["市场表现排名","公司规模排名","估值水平排名","财务状况排名"])
            )
            submitted1 = st.form_submit_button('分析确认')



        if submitted:
            tab1,tab2 = st.tabs(['Kpro','D3plt'])

            with tab1:
                st_pyecharts(Kpro.Kchart(stockCodeSel),height='750px')
                if stockCodeSel < '600000':
                    m = 0
                else:
                    m = 1 

                api.connect('121.36.81.195', 7709)               

                df3 = api.to_df(api.get_security_bars(8, m, stockCodeSel, 0, 720))
                df5 = api.to_df(api.get_security_bars(0, m, stockCodeSel, 0, 240))
                df13 = api.to_df(api.get_security_bars(0, m, stockCodeSel, 0, 624))
                df21 = api.to_df(api.get_security_bars(9, m, stockCodeSel, 0, 21))
                df55 = api.to_df(api.get_security_bars(9, m, stockCodeSel, 0, 55))
                df144 = api.to_df(api.get_security_bars(9, m, stockCodeSel, 0, 144))

                lsDF = [df3,df5,df13,df21,df55,df144]
                lsD = ['3D','5D',"13D","21D","55D","144D"]
                con = [720,240,624,21,55,144]
                plDF = pd.DataFrame()
                for n, df in enumerate(lsDF):
                    weights = norm(df,'vol',con[n])
                    weighted_data = np.repeat(df['close'], repeats=weights)
                    dDF = pd.DataFrame(weighted_data)
                    dDF['周期'] = lsD[n]
                    plDF = pd.concat([plDF,dDF])
                fig = px.violin(plDF,y='close',facet_col='周期',facet_col_spacing=0.01,box=True,violinmode='overlay',title='价格加权')
                st.plotly_chart(fig,theme=None)

            with tab2:
                scDF = pd.read_sql(stockCodeSel, eng)
                scDF['datetime'] = scDF['datetime'].astype('datetime64[ns]')
                figsc = px.scatter(scDF, x='datetime', y='open',size='amount', opacity=0.6, color='close',trendline='ewm',trendline_options={'ignore_na': True,'span':3, 'min_periods':8})
                figsc.update_layout(dragmode='pan',)
                st.plotly_chart(figsc, config={'scrollZoom': True,'displaylogo':False},theme=None)




                # n = 21
                # weights = norm(scDF.tail(n),'amount')
                # weighted_data = np.repeat(scDF['close'].tail(n), repeats=weights)
                # figwt = px.violin(weighted_data,box=True)
                # st.plotly_chart(figwt,theme=None)

        if submitted1:
            tab1,tab2 = st.tabs(['Kpro','D3plt'])
            with tab1:
                st_pyecharts(Kpro.Kchart(stockCodeSel),height='750px')
            with tab2:
                scDF = pd.read_sql(stockCodeSel, eng)
                scDF['datetime'] = scDF['datetime'].astype('datetime64[ns]')
                figsc = px.scatter(scDF, x='datetime', y='open',size='amount', opacity=0.6, color='close',trendline='ewm',trendline_options={'ignore_na': True,'span':3, 'min_periods':8})
                figsc.update_layout(dragmode='pan',)
                st.plotly_chart(figsc, config={'scrollZoom': True,'displaylogo':False},theme=None)

                # if stockCodeSel < '600000':
                #     m = 0
                # else:
                #     m = 1 

                # api.connect('121.36.81.195', 7709)               

                # df3 = api.to_df(api.get_security_bars(8, m, stockCodeSel, 0, 720))
                # df5 = api.to_df(api.get_security_bars(0, m, stockCodeSel, 0, 240))
                # df13 = api.to_df(api.get_security_bars(0, m, stockCodeSel, 0, 624))
                # df21 = api.to_df(api.get_security_bars(9, m, stockCodeSel, 0, 21))
                # df55 = api.to_df(api.get_security_bars(9, m, stockCodeSel, 0, 55))
                # df144 = api.to_df(api.get_security_bars(9, m, stockCodeSel, 0, 144))

                # lsDF = [df3,df5,df13,df21,df55,df144]
                # lsD = ['3D','5D',"13D","21D","55D","144D"]
                # con = [720,240,624,21,55,144]
                # plDF = pd.DataFrame()
                # for n, df in enumerate(lsDF):
                #     weights = norm(df,'vol',con[n])
                #     weighted_data = np.repeat(df['close'], repeats=weights)
                #     dDF = pd.DataFrame(weighted_data)
                #     dDF['周期'] = lsD[n]
                #     plDF = pd.concat([plDF,dDF])
                # fig = px.violin(plDF,y='close',facet_col='周期',facet_col_spacing=0.01,box=True,violinmode='overlay',title='价格加权')
                # st.plotly_chart(fig,theme=None)

            client = Quotes.factory(market='std')
            txt = client.F10(stockCodeSel, '行业分析')[116:]
            txt = txt.replace('│',' ')                
            txt = re.sub('([\u2500-\u25f7])','',txt)

            titlCode = re.findall(r'所属研究行业\S+', txt)[0]
            stockName = list(StockList[StockList['股票编码'] == stockCodeSel]['股票名称'])[0]
            
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
                lis = re.split(r"\s{3,}", dd[i])[-6:]
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
            Data['股票名称'] = Data['股票名称'].str.strip().str.replace(r'\s+', '', regex=True).str.replace('Ａ','A')

            def to_numeric_safe(value):
                try:
                    return pd.to_numeric(value)
                except (ValueError, TypeError):
                    return value

            ddf  = Data.map(to_numeric_safe)

            meddf = pd.merge(StockList,ddf,how='inner', on='股票名称')
            dddf = pd.concat([meddf,ddf]).drop_duplicates(subset=['股票名称']).reset_index(drop=True)


            fig = px.bar(dddf, y=dddf.columns[1], x=dddf.columns[2:], title=anCode,
                        barmode='relative', hover_name=dddf.columns[0],text_auto='')
            # fig.update_layout(dragmode='pan',legend_itemclick='toggleothers',)
            fig.update_layout(dragmode='pan',)


            tab3, tab4 = st.tabs([titlCode[7:],stockCodeSel+' : '+stockName])
            with tab3:
                stta = dddf.style.background_gradient(cmap='Blues')
                stta = stta.format('{:,.2f}', subset=list(dddf.columns[2:]))    
                st.dataframe(stta, hide_index=True, on_select='rerun',use_container_width=True)
            with tab4:
                st.plotly_chart(fig,config={'scrollZoom':True})