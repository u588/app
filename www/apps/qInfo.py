import streamlit as st
import plotly.express as px
from streamlit_echarts import st_pyecharts
from chart import Kpro,indexChart,d3plt,detailChart,gganChart,gganPx,fenX
from mootdx.quotes import Quotes
import pandas as pd
import numpy as np 
import re
from sqlalchemy import create_engine
from pytdx.hq import TdxHq_API
api = TdxHq_API()

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxFS')
engS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxStocks')
engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')



topDF = pd.read_sql('Top', engB)
bizDF = pd.read_sql('mBiz', engB).dropna(subset='营业收入(元)')
bzPDF = pd.read_sql('BizP', engB)


bizDF.loc[bizDF[bizDF['营业收入(元)'].str.endswith('万')].index,'营业收入(元)'] = bizDF[bizDF['营业收入(元)'].str.endswith('万')]['营业收入(元)'].str.replace('万','').astype(float)/10000
bizDF.loc[list(bizDF['营业收入(元)'].str.endswith('亿').dropna().index),'营业收入(元)'] = bizDF.loc[list(bizDF['营业收入(元)'].str.endswith('亿').dropna().index),'营业收入(元)'].str.replace('亿','').astype(float)

bizDF[['毛利率(%)','收入比例(%)','利润比例(%)']] = bizDF[['毛利率(%)','收入比例(%)','利润比例(%)']].astype('float')
bizDF.rename(columns={'营业收入(元)':'营业收入(亿元)'},inplace=True) 


StockList = pd.read_sql('StocksList', engS)[['code','name']]
StockList.columns=['股票编码','股票名称']

def norm(df, column_name, n):
    min_val = df[column_name].min()
    max_val = df[column_name].max()
    normalized_column = (df[column_name] - min_val) / (max_val - min_val)
    scaled_column = normalized_column * (n - 1) + 1
    discrete_scaled_column = scaled_column.round().astype(int)
    return discrete_scaled_column


def app():
    
    with st.form('form2'):
        with st.sidebar:
            stockCode = st.text_input(label='股票查询', value='')
            qf10 = st.selectbox(
                            'F10信息',
                            (
                            '公司概况',
                            '最新提示',
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

        bzdf = bzPDF[bzPDF['StockCode'] == stockCode]
        bidf = bizDF[bizDF['StockCode'] == stockCode]
        topdf = topDF[topDF['StockCode'] == stockCode]
        dqdf = bidf[bidf['项目名'].str.endswith('(地区)')]
        hydf = bidf[bidf['项目名'].str.endswith('(行业)')]
        cpdf = bidf[bidf['项目名'].str.endswith('(产品)')]


        tab1,tab2 ,tab3,tab4,tab5,tab6 = st.tabs(['Kpro','D3plt','F10','题材','主营','前五商业占比'])
        with tab1:
            st_pyecharts(Kpro.Kchart(stockCode),height='750px')
            if stockCode < '600000':
                m = 0
            else:
                m = 1 

            api.connect('121.36.81.195', 7709)               

            df3 = api.to_df(api.get_security_bars(8, m, stockCode, 0, 720))
            df5 = api.to_df(api.get_security_bars(0, m, stockCode, 0, 240))
            df13 = api.to_df(api.get_security_bars(0, m, stockCode, 0, 624))
            df21 = api.to_df(api.get_security_bars(9, m, stockCode, 0, 21))
            df55 = api.to_df(api.get_security_bars(9, m, stockCode, 0, 55))
            df144 = api.to_df(api.get_security_bars(9, m, stockCode, 0, 144))

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





            # st.bokeh_chart(BokK.K(stockCode))
            # st.header('财务分析')
            # st_pyecharts(detailChart.line(stockCode))
        with tab2:
            scDF = pd.read_sql(stockCode, engS)
            scDF['datetime'] = scDF['datetime'].astype('datetime64[ns]')
            figsc = px.scatter(scDF, x='datetime', y='open',size='amount', opacity=0.6, color='close',trendline='ewm',trendline_options={'ignore_na': True,'span':3, 'min_periods':8})
            figsc.update_layout(dragmode='pan',)
            st.plotly_chart(figsc, config={'scrollZoom': True,'displaylogo':False},theme=None)

            # st.bokeh_chart(d3plt.d3(stockCode),use_container_width=True)
        with tab3:
            st.subheader(qf10)
            st.text(txt)
            # st.markdown(txt)
        with tab4:
            topstl = topdf.style.background_gradient(cmap='Blues')
            # stta = stta.format('{:,.2f}', subset=list(dddf.columns[2:]))
            st.dataframe(topstl, hide_index=True,use_container_width=True)
        with tab5:
            # bistl = bidf.style.background_gradient(cmap='Blues')
            # sbistl = bistl.format('{:,.2f}', subset=list(bistl.columns[5:]))
            st.subheader('行 业')
            st.dataframe(hydf, hide_index=True,use_container_width=True)
            st.subheader('产 品')
            st.dataframe(cpdf, hide_index=True,use_container_width=True)
            st.subheader('地 区')
            st.dataframe(dqdf, hide_index=True,use_container_width=True)
        with tab6:
            bzstl = bzdf.style.background_gradient(cmap='Blues')
            # stta = stta.format('{:,.2f}', subset=list(dddf.columns[2:]))
            st.dataframe(bzstl, hide_index=True,use_container_width=True)

    with st.form('form3'):
        FSCode = pd.read_sql('FSCode',eng)
        eng.dispose()
        anData = FSCode[['L1Code','L1Name']].drop_duplicates().reset_index(drop=True).loc[1:13].reset_index(drop=True)
        with st.sidebar:
            anName = st.selectbox(
                '个股专业财务分析',
                (list(anData['L1Name']))
            )   
            submitted = st.form_submit_button('个股分析')

    if submitted:
        tab1,tab2,tab3 = st.tabs([anName+'Line',anName+'Bar','3'], )
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
                '中证分类聚合分析',
                ('每股指标',"资产负债表","利润表",'现金流量表','股本股东','发展能力分析','偿债能力分析','获利能力分析','经营能力分析','现金流分析','资本结构分析')
            )
            day = st.selectbox(
                '分析日期',
                (20230331,20230630,20230930,20231231,20240331,20240630,20240930)
            )
            leve = st.selectbox(
                '分类层级',
                (
                    'L3Name',
                    'L4Name'
                )
            )   
            submitted = st.form_submit_button('分类聚合')

            anCode = st.selectbox(
                '通达信行业分析',
                (["市场表现排名","公司规模排名","估值水平排名","财务状况排名"])
            )
            submitted1 = st.form_submit_button('行业分析')
        if submitted:
            fenX.fenChart(stockCode, list(anData[anData['L1Name']==fenCode]['L1Code'])[0],day, leve)

        if submitted1:
            fenX.fenChart(stockCode, list(anData[anData['L1Name']==fenCode]['L1Code'])[0],day,leve)
            client = Quotes.factory(market='std')
            txt = client.F10(stockCode, '行业分析')[116:]
            txt = txt.replace('│',' ')                
            txt = re.sub('([\u2500-\u25f7])','',txt)

            titlCode = re.findall(r'所属研究行业\S+', txt)[0]
            stockName = list(StockList[StockList['股票编码'] == stockCode]['股票名称'])[0]
            
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


            tab3, tab4 = st.tabs([titlCode[7:],stockCode+' : '+stockName])
            with tab3:
                stta = dddf.style.background_gradient(cmap='Blues')
                stta = stta.format('{:,.2f}', subset=list(dddf.columns[2:]))    
                st.dataframe(stta, hide_index=True, on_select='rerun',use_container_width=True)
            with tab4:
                st.plotly_chart(fig,config={'scrollZoom':True})