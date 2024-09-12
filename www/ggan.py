import pandas as pd
from sqlalchemy import create_engine
import streamlit as st



eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')

FSCode = pd.read_sql('FSCode',eng)
wCode  = pd.read_sql('wCode', eng)
stockCode = '600409'
anCode = 'XJL'

finRAW = pd.read_sql(stockCode, eng)
finRAW = pd.concat([finRAW,finRAW['report_date'].rename('Index')],axis=1)

midf = finRAW[wCode['Code']]*10000
rdf = finRAW[list(set(finRAW.columns).difference(set(wCode['Code'])))]
finW = pd.concat([rdf,midf],axis=1)

trsfin = finW.set_index('Index').T
trsfin = trsfin.reset_index().rename(columns={'index':'Code'})

sfin = pd.merge(FSCode,trsfin,on='Code',how='inner')

def getDF(anCode):
    match anCode:
        case "JYNL":
            df = sfin.query('L2Code=="JYNL" ')
            return(df)
        case "CZNL":
            df = sfin.query('L3Code=="CZNL" ')
            return(df)
        case "HLNL":
            df = sfin.query('L2Code=="HLNL" ')
            return(df)
        case "FZNL":
            df = sfin.query('L2Code=="FZNL" ')
            return(df)
        case "GB":
            df = sfin.query('L2Code=="GB" ')
            return(df)
        case "DJ":
            df = sfin.query('L2Code=="DJ" ')
            return(df)
        case "MGZB":
            df = sfin.query('L3Code=="MGZB" ')
            return(df)
        case "XJL":
            df = sfin.query('L1Code=="XJL" and L3Code=="XJL" ')
            return(df)
        case "XJLL":
            df = sfin.query('L1Code=="XJLL" and (L3Code=="JE" or L3Code=="ZJE") ')
            return(df)
        case "LRB":
            df = sfin.query('L1Code=="LRB" and (L3Code=="TZSY" or L3Code=="YYLRHJ"  or L3Code=="LRZE" or L3Code=="JLR" or L3Code=="HJ" or L3Code=="ZHSYZE"  or L3Code=="JLRL") ')
            return(df)
        case "ZCFZ":
            df = sfin.query('L1Code=="ZCFZ" and (L3Code=="HJ" or L3Code=="ZJ") ')
            return(df)
        case "ZBJG":
            df = sfin.query('L1Code=="ZBJG" ')
            return(df)
        case "JGCG":
            df = sfin.query('L1Code=="JGCG" ')
            return(df)
df = getDF(anCode)

import plotly.express as px
fig = px.bar(df, x='cnName', y=list(df.columns[-84:]) ,barmode='group')
fig.update_layout(dragmode='pan',legend_itemclick='toggleothers')

lis1 = list(filter(lambda x: '0331' in x, list(map(str,df.columns))))
fig1 = px.bar(df, x='cnName', y=list(map(int,lis1)) ,barmode='group')
fig1.update_layout(dragmode='pan',legend_itemclick='toggleothers')
lis2 = list(filter(lambda x: '0630' in x, list(map(str,df.columns))))
fig2 = px.bar(df, x='cnName', y=list(map(int,lis2)) ,barmode='group')
fig2.update_layout(dragmode='pan',legend_itemclick='toggleothers')
lis3 = list(filter(lambda x: '0930' in x, list(map(str,df.columns))))
fig3 = px.bar(df, x='cnName', y=list(map(int,lis3)) ,barmode='group')
fig3.update_layout(dragmode='pan',legend_itemclick='toggleothers')
lis4 = list(filter(lambda x: '1231' in x, list(map(str,df.columns))))
fig4 = px.bar(df, x='cnName', y=list(map(int,lis4)) ,barmode='group')
fig4.update_layout(dragmode='pan',legend_itemclick='toggleothers')

tab1, tab2 = st.tabs(['1','2'])
with tab1:
    st.plotly_chart(fig,config={'scrollZoom':True})
with tab2:
    st.plotly_chart(fig1,config={'scrollZoom':True})
    st.plotly_chart(fig2,config={'scrollZoom':True})
    st.plotly_chart(fig3,config={'scrollZoom':True})
    st.plotly_chart(fig4,config={'scrollZoom':True})