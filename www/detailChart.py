import re
from pyecharts.charts.composite_charts.grid import Grid
from pyecharts.options.global_options import InitOpts
from sqlalchemy import create_engine
import pandas as pd
import numpy as np
from pyecharts.components import Table
from pyecharts.charts import Pie, Line
from pyecharts import options as opts
from pyecharts.options import ComponentTitleOpts


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')
engD = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/StockFina')
engF = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds')

def line(StockID) -> Line:
    Data = pd.read_sql(StockID, engD).fillna('0').applymap(lambda x : x.replace('%', ''))
    d = Data[['date','nProfit','nProfit_yoy','totalRevenue','tr_yoy','eps', 'bps','capital_rese_ps', 'undist_profit_ps', 'ocfps', 'nProfit_margin', 
    'gProfit_margin', 'roe', 'debt_to_eqt', 'debt_to_assets']].loc[0]
    dd = Data.loc[1:].tail(61).set_index('date').astype(float).round(2)
    dd['nProfit'] = (dd['nProfit']/100000000).round(2)
    dd['dtnProfit'] = (dd['dtnProfit']/100000000).round(2)
    dd['totalRevenue'] = (dd['totalRevenue']/100000000).round(2)
    dd.reset_index(inplace=True)

    d1s = dd[['date','nProfit','nProfit_yoy','totalRevenue','tr_yoy','eps', 'bps','capital_rese_ps', 'undist_profit_ps', 'ocfps', 'nProfit_margin', 
    'gProfit_margin', 'roe', 'debt_to_eqt', 'debt_to_assets']]
    # d2s = dd[['date','sIndex','pe_lyr_ly','pr_ttm_ly','pb_ly']]
    # d1g = d1s.groupby('sIndex')
    # inName = d1g.head(1).sIndex.tolist()
    date = dd.drop_duplicates(subset=('date'), keep='first').date.to_list()
    c = (
        Line(opts.InitOpts(page_title='财务分析',width="1330px", height="600px"))
        .add_xaxis(date)
        .set_global_opts(legend_opts=opts.LegendOpts(type_='scroll',orient='vertical',pos_right='-1%',pos_top='10%',is_show=True),title_opts=opts.TitleOpts(title=StockID, pos_left="center",pos_top="5"),)
    )
    for i, n in enumerate(d.tolist()[1:]):
        c.add_yaxis(d.tolist()[1:][i], d1s[d1s.columns[i+1]].tolist(),is_smooth=True, label_opts=opts.LabelOpts(is_show=False),is_selected=False)
    return c


def pie(StockID):

    # StocksList = pd.read_csv('/home/ts/app/data/StocksList.csv', dtype={'code':'object'})
    StocksList = pd.read_sql('StocksCode', dtype={'StockCode':'object'})
    Stock = StocksList.loc[StocksList['StockCode']==StockID].astype(str).reset_index()

    IndexConst = pd.read_sql('IndexCons', eng)
    StockInIndex = IndexConst[IndexConst.StockCode==StockID][['IndexCode', 'StockCode','StockName']]
    # StockInIndex.rename(columns={'name':'stock_name','code':'stock_code'}, inplace=True)
    csIndex = pd.read_sql('tdxIndexs', eng)
    csIndex =csIndex[['IndexCode', 'IndexName']]

    data = pd.merge(StockInIndex, csIndex, on='IndexCode')  

    dd = data[['IndexName', 'IndexCode']]
    d = data.StockName[0]+" : " + data.StockCode[0]
    c = (
        Pie()
        .add(
            "",
            [list(z) for z in zip(dd.IndexName, dd.IndexCode)],
            radius=["25%", "70%"],
            center=["50%", "50%"],
            rosetype="area",
        )
        .set_global_opts(
                        title_opts=opts.TitleOpts(
                                    title=(d),pos_left="center",pos_top="20",
                          
                        #             subtitle = ('所属行业: '+Stock['industry'][0]+'  地域: '+Stock['area'][0]+'  市盈率: '+Stock['pe'][0]+'  总股本: '+Stock['totals'][0]+'亿元'+
                        #     '  流通股本: '+Stock['outstanding'][0]+'亿元'+'  市净率:'+Stock['pb'][0]+'  每股收益:'+Stock['esp'][0]+ '  每股净资:'+Stock['bvps'][0]+
                        #     '  每股分配利润:'+Stock['perundp'][0]+'  收入同比:'+Stock['rev'][0]+'%'+'  利润同比:'+Stock['profit'][0]+'%'+'  毛利率:'+Stock['gpr'][0]+'%'+
                        #     '  净利润率:'+Stock['npr'][0]+'%'), 
                        #             subtitle_textstyle_opts=opts.TextStyleOpts(color='blue',font_style='italic',font_weight='bold'),
                        ),
                        legend_opts=opts.LegendOpts(is_show=False),
        )
        .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    )
    return c


