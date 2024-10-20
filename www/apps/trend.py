import streamlit as st
from streamlit_echarts import st_pyecharts
from mootdx.quotes import Quotes
from chart import makSum
import re
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine
from chart import Kpro,indexChart,d3plt,detailChart,gganChart,gganPx,fenX

engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/StockBas')
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/smDaily')
engTDX = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')

topDF = pd.read_sql('Top', engB)
bizDF = pd.read_sql('mBiz', engB).dropna(subset='营业收入(元)')
bizDF.loc[bizDF[bizDF['营业收入(元)'].str.endswith('万')].index,'营业收入(元)'] = bizDF[bizDF['营业收入(元)'].str.endswith('万')]['营业收入(元)'].str.replace('万','').astype(float)/10000
bizDF.loc[list(bizDF['营业收入(元)'].str.endswith('亿').dropna().index),'营业收入(元)'] = bizDF.loc[list(bizDF['营业收入(元)'].str.endswith('亿').dropna().index),'营业收入(元)'].str.replace('亿','').astype(float)

bizDF[['毛利率(%)','收入比例(%)','利润比例(%)']] = bizDF[['毛利率(%)','收入比例(%)','利润比例(%)']].astype('float') 
tdxData = pd.read_sql('tdxIndexsData', engTDX)






def app():

    tdxData = pd.read_sql('tdxIndexsData', engTDX).sort_values('3D',ascending=False)
    ptData = tdxData.style.background_gradient(cmap='Blues')
    ptData = ptData.format('{:,.2f}', subset=list(tdxData.columns[2:]))
    # fig = px.scatter_ternary(tdxData,a='3D',b='5D',c='21D',hover_name='IndexName')
    fig1 = px.scatter_3d(tdxData,x='3D',y='5D',z='21D',color='55D',hover_name='IndexName',height=600)
    # with st.form('form'):
    tab1,tab2 =st.tabs(['1','2'])
    with tab1:
        # st.plotly_chart(fig)
        st.dataframe(ptData, hide_index=True,use_container_width=True,height=600)
    with tab2:
        st.plotly_chart(fig1, use_container_width=True)
        # st_pyecharts(makSum.testti(),height='500px',width="100%")
    # with tab3:
    #     st_pyecharts(makSum.testti(),height='600px',width="100%")

    with st.form('form0'):
        with st.sidebar:
            indexCode = st.text_input(label='指数代码',value='')
            submitted0 = st.form_submit_button('确认')
        if submitted0:

            st_pyecharts(indexChart.Kchart(indexCode),height='600px')


    with st.form('form1'):
        with st.sidebar:
            txt = st.text_input(label='题材模糊查询', value='')
            submitted1 = st.form_submit_button('确认')
        if submitted1:
            txtDF = topDF[topDF['题材'].str.contains(txt, na=False)].sort_values(by=['相关度','StockCode'], ascending=False).reset_index(drop=True)
            prdDF = bizDF[bizDF['项目名'].str.endswith('(产品)')][bizDF[bizDF['项目名'].str.endswith('(产品)')]['日期']=='2024-06-30'].reset_index(drop=True)
            prdDF['项目名'] = prdDF['项目名'].str.replace('(产品)', '')
            prDF = prdDF[prdDF['StockCode'].isin(list(txtDF['StockCode']))]
            plData = prDF[prDF['收入比例(%)'].astype(float)>15]

            tab11,tab12 =st.tabs(['1','2'])
            with tab11:
                st.dataframe(txtDF, hide_index=True,use_container_width=True,height=600,on_select='rerun')
            with tab12:
                st.dataframe(plData, hide_index=True,use_container_width=True,height=600,on_select='rerun')

            # txDF = txtDF.style.background_gradient(cmap='Blues')
            # txDF = txDF.format('{:,.2f}', subset=list(txtDF.columns[2:]))
            # st.dataframe(txtDF, hide_index=True,use_container_width=True,height=600,on_select='rerun')
            

    with st.form('form2'):
        with st.sidebar:
            txt = st.text_input(label='行业模糊查询', value='')
            trdDate = st.selectbox('日期',('2024-06-30','2023-12-31'))
            submitted1 = st.form_submit_button('确认')

        if submitted1:
            trdDF = bizDF[bizDF['项目名'].str.endswith('(行业)')][bizDF[bizDF['项目名'].str.endswith('(行业)')]['日期']==trdDate].reset_index(drop=True)
            trdDF['项目名'] = trdDF['项目名'].str.replace('(行业)', '')
            trdSe = trdDF[trdDF['项目名'].str.contains(txt, na=False)]
            pltData = trdSe[trdSe['收入比例(%)'].astype(float)>15]

            st.dataframe(pltData, hide_index=True,use_container_width=True,height=600,on_select='rerun')

    with st.form('form3'):
        with st.sidebar:
            txt = st.text_input(label='产品模糊查询', value='')
            submitted1 = st.form_submit_button('确认')

        if submitted1:
            prdDF = bizDF[bizDF['项目名'].str.endswith('(产品)')][bizDF[bizDF['项目名'].str.endswith('(产品)')]['日期']==trdDate].reset_index(drop=True)

            prdDF['项目名'] = prdDF['项目名'].str.replace('(产品)', '')
            prdSe = prdDF[prdDF['项目名'].str.contains(txt, na=False)]
            pltData = prdSe[prdSe['收入比例(%)'].astype(float)>15]

            st.dataframe(pltData, hide_index=True,use_container_width=True,height=600,on_select='rerun')

    with st.form('form4'):
        with st.sidebar:
            stockCode = st.text_input(label='股票查询', value='')
            qf10 = st.selectbox(
                            'F10信息',
                            ('最新提示',
                            '公司概况',
                            '热点题材',
                            '公司公告',
                            '公司报道',
                            '经营分析',
                            '行业分析',
                            '价值分析',)
                        )            
            submitted4 = st.form_submit_button('确认')
    if submitted4:
        client = Quotes.factory(market='std')
        # a = client.F10C(symbol=stockCode)
        txt = client.F10(stockCode, qf10)
        try:
            txt = txt[:txt.find('〖免责条款〗')]
        except:
            pass
        txt = txt.replace('│',' ')                
        txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符         


        st.subheader(qf10)
        st.text(txt)
            # st.markdown(txt)

