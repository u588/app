from pyecharts.charts.composite_charts.grid import Grid
from sqlalchemy import create_engine
import pandas as pd
from pyecharts.charts import Line
from pyecharts import options as opts
import streamlit as st

@st.cache_data
def gChart(stockCode, anCode):
    eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56:5432/tdxFS')

    FSCode = pd.read_sql('FSCode',eng)
    wCode  = pd.read_sql('wCode', eng)

    finRAW = pd.read_sql(stockCode, eng)
    eng.dispose()
    finRAW = pd.concat([finRAW,finRAW['report_date'].rename('Index')],axis=1)

    midf = finRAW[wCode['Code']]*10000
    rdf = finRAW[list(set(finRAW.columns).difference(set(wCode['Code'])))]
    finW = pd.concat([rdf,midf],axis=1)

    trsfin = finW.set_index('Index').T
    trsfin = trsfin.reset_index().rename(columns={'index':'Code'})

    sfin = pd.merge(FSCode,trsfin,on='Code',how='inner')
    N = sfin.shape[1]-9

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

    df = getDF(anCode).reset_index(drop=True)
    d = list(df['cnName'])

    dateA = list(map(str, df.columns[-N:]))
    DataA = df[df.columns[-N:]]

    dateD = list(filter(lambda x: '1231' in x, list(map(str,df.columns))))
    DataD = df[list(map(int,dateD))]
    dateM = list(filter(lambda x: '0331' in x, list(map(str,df.columns))))
    DataM = df[list(map(int,dateM))]
    dateJ = list(filter(lambda x: '0630' in x, list(map(str,df.columns))))
    DataJ = df[list(map(int,dateJ))]
    dateS = list(filter(lambda x: '0930' in x, list(map(str,df.columns))))
    DataS = df[list(map(int,dateS))]

    def pltL(date, Data):
        c = (
            # Line(opts.InitOpts(page_title='财务分析',width="1800px", height="600px"))
            # Line(opts.InitOpts(width="1800px", height="600px"))
            Line()
            .add_xaxis(date)
            .set_global_opts(
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False), 
                # legend_opts=opts.LegendOpts(type_='scroll',pos_top='8%',is_show=True ,selector=True),
                legend_opts=opts.LegendOpts(type_='scroll',pos_top='10%',pos_right='-1%',is_show=True ,selector=True,orient='vertical',item_width=15),
                # title_opts=opts.TitleOpts(title=StockID, pos_left="center",pos_top="2"),
                datazoom_opts=[
                    opts.DataZoomOpts(xaxis_index=[0, 4],is_show=False, type_="inside",range_start=0, range_end=100),
                    opts.DataZoomOpts(xaxis_index=[0, 1],is_show=False, range_start=0, range_end=100,pos_top='99%',),
                    opts.DataZoomOpts(xaxis_index=[0, 2],is_show=False, range_start=0, range_end=100,pos_top='99%',),
                    opts.DataZoomOpts(xaxis_index=[0, 3],is_show=False, range_start=0, range_end=100,pos_top='99%',),
                    opts.DataZoomOpts(xaxis_index=[0, 0],is_show=False, range_start=0, range_end=100,pos_top='99%',),
                ],

                )
            )
        for i ,n in enumerate(d):
            # try:
            c.add_yaxis(
                series_name=n, 
                y_axis=list(Data.loc[i]),
                is_smooth=True,
                label_opts=opts.LabelOpts(is_show=False),
            )
        return(c)
    grid_chart = (Grid(opts.InitOpts(width="1800px", height="600px"))
                .add(pltL(dateD,DataD), grid_opts=opts.GridOpts(border_width=0, pos_left="6%", pos_right="16%",pos_top='5%',height='12%',))
                .add(pltL(dateM,DataM), grid_opts=opts.GridOpts(border_width=0, pos_left="6%", pos_right="16%",pos_top='24%',height='12%',))
                .add(pltL(dateJ,DataJ), grid_opts=opts.GridOpts(border_width=0, pos_left="6%", pos_right="16%",pos_top='43%',height='12%',))
                .add(pltL(dateS,DataS), grid_opts=opts.GridOpts(border_width=0, pos_left="6%", pos_right="16%",pos_top='63%',height='12%',))
                .add(pltL(dateA,DataA), grid_opts=opts.GridOpts(border_width=0, pos_left="6%", pos_right="16%",pos_top='80%',height='9%',))
                )
    return(grid_chart)
# st_pyecharts(grid_chart,width="100%",height="600px")

