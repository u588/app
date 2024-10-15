import streamlit as st
import numpy as np 
import re
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
engI = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')


lsDate = list(range(2000,2026))

def app():
    with st.form('form0'):
        with st.sidebar:
            Code = st.selectbox('市场', ('指数','股票'))
            inCode = st.text_input(label='代码', value='')
            loDate = st.selectbox('开始日期',lsDate)
            hiDate = st.selectbox('截止日期',lsDate)
            submitted0 = st.form_submit_button('分析')
        if submitted0:
            match Code:
                case "指数":
                    iCode = pd.read_sql("tdxIndexs", engI)
                    Name = list(iCode[iCode['IndexCode']==inCode]['IndexName'])[0]
                    idxDF = pd.read_sql(inCode, engI)
                    engI.dispose()

                case "股票":
                    sCode = pd.read_sql('StocksList', engS)
                    Name = list(sCode[sCode['code']==inCode]['name'])[0]
                    idxDF = pd.read_sql(inCode, engS)
                    engS.dispose()

             
            
            plDF = idxDF[(idxDF['year']>loDate) & (idxDF['year']<hiDate)]
            fig1 = px.density_heatmap(plDF, x='day',y='month',z='amount',histfunc='sum',histnorm='percent',nbinsx=35,nbinsy=12,text_auto='.2r',title='总 计',)
            # fig2 = px.density_heatmap(plDF, x='day',y='month',z='amount',histfunc='avg',histnorm='percent',nbinsx=35,nbinsy=12,text_auto='.2r',title='平 均')
            fig3 = px.density_heatmap(plDF, x='day',y='month',z='amount',histfunc='max',histnorm='percent',nbinsx=35,nbinsy=12,text_auto='.2r',title='最 大')
            fig4 = px.density_heatmap(plDF, x='day',y='month',z='amount',histfunc='min',histnorm='percent',nbinsx=35,nbinsy=12,text_auto='.2r',title='最 小')
            
            st.subheader(Name)
            st.plotly_chart(fig1,theme=None)
            # st.plotly_chart(fig2,theme=None)
            st.plotly_chart(fig3,theme=None)
            st.plotly_chart(fig4,theme=None)
