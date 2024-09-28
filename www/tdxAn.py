from mootdx.quotes import Quotes
import pandas as pd
import plotly.express as px
import re
import streamlit as st


qf10='行业分析'
anCode = '估值水平排名'
StockCode = '600996'


client = Quotes.factory(market='std')
txt = client.F10(StockCode, qf10)[116:]

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
# fig.show(config={'scrollZoom':True})



tab1, tab2 = st.tabs(['1','2'])
with tab1:
    st.dataframe(ddf.style.highlight_max(axis=0))
with tab2:
    st.plotly_chart(fig,config={'scrollZoom':True})
