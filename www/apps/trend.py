import streamlit as st
from streamlit_echarts import st_pyecharts
from mootdx.quotes import Quotes
# from chart import makSum
import re
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine
# from chart import Kpro,indexChart,d3plt,detailChart,gganChart,gganPx,fenX,getConsStock
from chart import Kpro,indexChart,getConsStock

engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')
eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56:5432/smDaily')
engTDX = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56:5432/tdxIndex')
engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56:5432/tdxStocks')

opIndex= pd.read_sql('optIndexs',engTDX)
topDF = pd.read_sql('Top', engB)
bizDF = pd.read_sql('mBiz', engB).dropna(subset='营业收入(元)')
bizDF.loc[bizDF[bizDF['营业收入(元)'].str.endswith('万')].index,'营业收入(元)'] = bizDF[bizDF['营业收入(元)'].str.endswith('万')]['营业收入(元)'].str.replace('万','').astype(float)/10000
bizDF.loc[list(bizDF['营业收入(元)'].str.endswith('亿').dropna().index),'营业收入(元)'] = bizDF.loc[list(bizDF['营业收入(元)'].str.endswith('亿').dropna().index),'营业收入(元)'].str.replace('亿','').astype(float)

bizDF[['毛利率(%)','收入比例(%)','利润比例(%)']] = bizDF[['毛利率(%)','收入比例(%)','利润比例(%)']].astype('float') 
tdxData = pd.read_sql('tdxIndexsData', engTDX)


def normalize(x):
    return (x - x.min()) / (x.max() - x.min())
@st.cache_data
def plD(indexCode):
    indexName = opIndex[opIndex['IndexCode']==indexCode]['IndexName'].values[0]
    selDF = pd.read_sql(indexCode, engTDX)

    shDF = pd.read_sql('000001', engTDX)
    szDF = pd.read_sql('399001', engTDX)
    hs300DF = pd.read_sql('000300', engTDX)
    csa500DF = pd.read_sql('000510', engTDX)
    cs500DF = pd.read_sql('000905', engTDX)
    sh50DF = pd.read_sql('000016', engTDX)
    kc50DF = pd.read_sql('000688', engTDX)
    cs1000DF = pd.read_sql('000852', engTDX)
    plData = pd.DataFrame()
    plData['datetime'] = shDF['datetime'].reset_index(drop=True)

    plData = pd.merge(plData,selDF[['datetime','close']].rename(columns={'close':indexName}),on='datetime',how='outer')
    plData = pd.merge(plData,shDF[['datetime','close']].rename(columns={'close':'上证指数'}),on='datetime',how='outer')
    plData = pd.merge(plData,szDF[['datetime','close']].rename(columns={'close':'深证成指'}),on='datetime',how='outer')
    plData = pd.merge(plData,hs300DF[['datetime','close']].rename(columns={'close':'沪深300'}),on='datetime',how='outer')
    plData = pd.merge(plData,csa500DF[['datetime','close']].rename(columns={'close':'中证A500'}),on='datetime',how='outer')
    plData = pd.merge(plData,cs500DF[['datetime','close']].rename(columns={'close':'中证500'}),on='datetime',how='outer')
    plData = pd.merge(plData,sh50DF[['datetime','close']].rename(columns={'close':'上证50'}),on='datetime',how='outer')
    plData = pd.merge(plData,kc50DF[['datetime','close']].rename(columns={'close':'科创50'}),on='datetime',how='outer')
    plData = pd.merge(plData,cs1000DF[['datetime','close']].rename(columns={'close':'中证1000'}),on='datetime',how='outer')
    return(plData)   
 
def plfig(nday,indexCode):
    plData = plD(indexCode).tail(nday)
    ddd = plData.set_index('datetime').apply(normalize, axis=0)                  
    fig = px.line(ddd.reset_index(),x='datetime', y=plData.columns,line_shape='linear')
    fig.update_xaxes(showspikes=True, spikecolor="black", spikesnap="cursor", spikemode="across",spikethickness=0.6)
    fig.update_yaxes(showspikes=True, spikecolor="black", spikesnap="cursor", spikemode="across",spikethickness=0.6)
    fig.update_traces(hovertemplate='%{y:.2f}')
    fig.update_layout(hovermode='x')
    return(fig)    

def sData(Data):
    # D = pd.read_sql('IndexCons',engTDX)
    # # d = pd.DataFrame(columns=['code','PCB']).astype(dtype={'PCB':float})
    # Data = D.loc[D['IndexCode']== indexCode].reset_index(drop=True)
    StockLists = Data[['StockCode','StockName']].values.tolist()
    shDF = pd.read_sql('000001', engTDX)
    plData = pd.DataFrame()
    plData['datetime'] = shDF['datetime'].reset_index(drop=True)
    plData = pd.merge(plData,shDF[['datetime','close']].rename(columns={'close':'上证指数'}),on='datetime',how='outer')
    for Stock in StockLists:
        plData = pd.merge(plData,pd.read_sql(Stock[0],engS)[['datetime','close']].rename(columns={'close':Stock[1]}),on='datetime',how='outer')
    return(plData)
        
def pltsData(nday,Data):
    plData = sData(Data).tail(nday)
    ddd = plData.set_index('datetime').apply(normalize, axis=0)                  
    fig = px.line(ddd.reset_index(),x='datetime', y=plData.columns,line_shape='linear')
    fig.update_xaxes(showspikes=True, spikecolor="black", spikesnap="cursor", spikemode="across",spikethickness=0.6)
    fig.update_yaxes(showspikes=True, spikecolor="black", spikesnap="cursor", spikemode="across",spikethickness=0.6)
    fig.update_traces(hovertemplate='%{y:.2f}')
    fig.update_layout(hovermode='x')
    fig.update_layout(dragmode='pan',legend_itemclick='toggleothers')
    return(fig)    

def viData(tdxData):
    df=pd.DataFrame()
    cl=['3D','5D','21D','55D']
    for ls in cl:
        dff = pd.DataFrame()
        dff = tdxData[list(tdxData.columns[:2])+[ls]].copy()
        dff.rename(columns={ls:'vol'},inplace=True)
        dff['周期'] = ls
        df = pd.concat([df,dff])
    return(df)

def app():
    tdxData = pd.read_sql('tdxIndexsData', engTDX).sort_values('3D',ascending=False)
    ptData = tdxData.style.background_gradient(cmap='Blues')
    ptData = ptData.format('{:,.2f}', subset=list(tdxData.columns[2:]))
    # fig = px.scatter_ternary(tdxData,a='3D',b='5D',c='21D',hover_name='IndexName')
    fig1 = px.scatter_3d(tdxData,x='3D',y='5D',z='21D',color='55D',hover_name=tdxData.IndexCode +' : '+tdxData.IndexName,height=600)
    # with st.form('form'):
    tab1m,tab2m =st.tabs(['详 单','分 布'])
    with tab1m:
        # st.plotly_chart(fig)
        st.dataframe(ptData, hide_index=True,use_container_width=True,height=600)
        vdf = viData(tdxData)
        figv = px.violin(vdf,y='vol',box=True,points='all',hover_name=vdf.IndexCode+' : '+vdf.IndexName,facet_col='周期',facet_col_spacing=0.03,violinmode='overlay')
        st.plotly_chart(figv)
    with tab2m:
        st.plotly_chart(fig1, use_container_width=True)
        # st_pyecharts(makSum.testti(),height='500px',width="100%")
    # with tab3:
    #     st_pyecharts(makSum.testti(),height='600px',width="100%")

    with st.form('form0'):
        with st.sidebar:
            indexCode = st.text_input(label='指数代码',value='')
            submitted0 = st.form_submit_button('指数查询')

            stockCodesel = st.text_input(label='股票查询', value='')


            qf10 = st.selectbox(
                            'F10信息',
                            ('最新提示',
                            '公司概况',
                            '热点题材',
                            '公司公告',
                            '公司报道',
                            '经营分析',
                            '行业分析',
                            '研报评级',)
                        )
            submitted5 = st.form_submit_button('股票查询')            
            # submitted4 = st.form_submit_button('F10查询')            

            stockCode = getConsStock.getStock(indexCode)
            pltCode = stockCode.style.background_gradient(cmap='Blues')
            pltCode = pltCode.format('{:,.2f}', subset=list(tdxData.columns[2:]))
        if submitted0:
            tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs(['K 线','13天指数比较','21天指数比较','3个月指数比较','半年指数比较','1年指数比较','3年指数比较','5年指数比较'])
            with tab1:
                st_pyecharts(indexChart.Kchart(indexCode),height='600px')
            with tab2:
                st.plotly_chart(plfig(13,indexCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab3:
                st.plotly_chart(plfig(21,indexCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab4:
                st.plotly_chart(plfig(55,indexCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab5:
                st.plotly_chart(plfig(144,indexCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab6:
                st.plotly_chart(plfig(233,indexCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab7:
                st.plotly_chart(plfig(610,indexCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab8:
                st.plotly_chart(plfig(1597,indexCode),config={'scrollZoom': True,'displaylogo':False},theme=None)

            fig1c = px.scatter_3d(stockCode,x='3D',y='5D',z='21D',color='55D',hover_name=stockCode.StockCode + ' : '+ stockCode.StockName,height=600)
            tab1c,tab2c =st.tabs(['详 单','分 布'])
            with tab1c:
                # st.plotly_chart(fig)
                st.dataframe(pltCode, hide_index=True,use_container_width=True,height=600)
                sdf = viData(stockCode)
                figs = px.violin(sdf,y='vol',box=True,points='all',hover_name=sdf.StockCode+' : '+sdf.StockName,facet_col='周期',facet_col_spacing=0.03,violinmode='overlay')
                st.plotly_chart(figs)
            with tab2c:
                st.plotly_chart(fig1c, use_container_width=True)
        if submitted5:
            fig1c = px.scatter_3d(stockCode,x='3D',y='5D',z='21D',color='55D',hover_name=stockCode.StockCode + ' : '+ stockCode.StockName,height=600)
            tab1c,tab2c =st.tabs(['详 单','分 布'])
            with tab1c:
                # st.plotly_chart(fig)
                st.dataframe(pltCode, hide_index=True,use_container_width=True,height=600)
            with tab2c:
                st.plotly_chart(fig1c, use_container_width=True)
            tab1s,tab2s,tab3s,tab4s,tab5s,tab6s,tab7s = st.tabs(['K 线','13天比较','21天比较','3个月比较','半年比较','1年比较','F10'])
            with tab1s:    
                st_pyecharts(Kpro.Kchart(stockCodesel),renderer='canvas',height='750px',key='k')
            with tab2s:
                st.plotly_chart(pltsData(13,stockCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab3s:
                st.plotly_chart(pltsData(21,stockCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab4s:
                st.plotly_chart(pltsData(55,stockCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab5s:
                st.plotly_chart(pltsData(144,stockCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab6s:
                st.plotly_chart(pltsData(233,stockCode),config={'scrollZoom': True,'displaylogo':False},theme=None)
            with tab7s:
                client = Quotes.factory(market='std')
                # a = client.F10C(symbol=stockCode)
                txt = client.F10(stockCodesel, qf10)
                try:
                    txt = txt[:txt.find('〖免责条款〗')]
                except:
                    pass
                txt = txt.replace('│',' ')                
                txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符         
                st.subheader(qf10)
                st.text(txt)                     



