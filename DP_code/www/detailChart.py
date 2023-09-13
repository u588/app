from pyecharts.charts.composite_charts.grid import Grid
from sqlalchemy import create_engine
import pandas as pd
from pyecharts.charts import Pie, Line
from pyecharts import options as opts



eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')
engD = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxFS')
engF = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds')

def line(StockID) -> Line:
    Data = pd.read_sql(StockID, engD)
    ll = list(Data.columns[0:10])+['col21','col27','col63','col86','col92','col131','col161']+list(Data.columns[183:203])+ list(Data.columns[209:215])+['col225','col228','col229','col246','col284','col502']
    # ll = list(Data.columns[0:10])
    Data = Data[ll]
    dn = pd.read_sql('tdxFSCode', engD)
    # d = Data[['date','nProfit','nProfit_yoy','totalRevenue','tr_yoy','eps', 'bps','capital_rese_ps', 'undist_profit_ps', 'ocfps', 'nProfit_margin', 
    # 'gProfit_margin', 'roe', 'debt_to_eqt', 'debt_to_assets']].loc[0]
    dd = Data.set_index('report_date')
    d = list(dd.columns)
    # dd['nProfit'] = (dd['nProfit']/100000000).round(2)
    # dd['dtnProfit'] = (dd['dtnProfit']/100000000).round(2)
    # dd['totalRevenue'] = (dd['totalRevenue']/100000000).round(2)
    dd.reset_index(inplace=True)

    d1s = dd
    # d2s = dd[['date','sIndex','pe_lyr_ly','pr_ttm_ly','pb_ly']]
    # d1g = d1s.groupby('sIndex')
    # inName = d1g.head(1).sIndex.tolist()
    date = dd.report_date.apply(str).to_list()
    c = (
        Line(opts.InitOpts(page_title='财务分析',width="1330px", height="600px"))
        .add_xaxis(date)
        .set_global_opts(xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False), legend_opts=opts.LegendOpts(type_='scroll',orient='horizontal',pos_right='0%',pos_top='95%',is_show=True),title_opts=opts.TitleOpts(title=StockID, pos_left="center",pos_top="5"),)
    )
    for i in d:
        try:
            c.add_yaxis(dn[(dn.Code==i)].cnName.tolist()[0], d1s[i].tolist(),is_smooth=True, label_opts=opts.LabelOpts(is_show=False),is_selected=False)
        except:
            pass
    grid_chart = Grid(opts.InitOpts(page_title='分析', width="1360px", height="650px"))

    grid_chart.add(c, grid_opts=opts.GridOpts(border_width=0, pos_left="8%", pos_right="5%",pos_bottom="10%"),)

    return grid_chart


# def pie(StockID):


#     StocksList = pd.read_sql('StocksCode',eng,  dtype={'StockCode':'object'})
#     Stock = StocksList.loc[StocksList['StockCode']==StockID].astype(str).reset_index()

#     IndexConst = pd.read_sql('IndexCons', eng)
#     StockInIndex = IndexConst[IndexConst.StockCode==StockID][['IndexCode', 'StockCode','StockName']]

#     csIndex = pd.read_sql('tdxIndexs', eng)
#     csIndex =csIndex[['IndexCode', 'IndexName']]

#     data = pd.merge(StockInIndex, csIndex, on='IndexCode')  

#     dd = data[['IndexName', 'IndexCode']]
#     d = data.StockName[0]+" : " + data.StockCode[0]
#     c = (
#         Pie()
#         .add(
#             "",
#             [list(z) for z in zip(dd.IndexName, dd.IndexCode)],
#             radius=["25%", "70%"],
#             center=["50%", "50%"],
#             rosetype="area",
#         )
#         .set_global_opts(
#                         title_opts=opts.TitleOpts(
#                                     title=(d),pos_left="center",pos_top="20",
                          
#                         #             subtitle = ('所属行业: '+Stock['industry'][0]+'  地域: '+Stock['area'][0]+'  市盈率: '+Stock['pe'][0]+'  总股本: '+Stock['totals'][0]+'亿元'+
#                         #     '  流通股本: '+Stock['outstanding'][0]+'亿元'+'  市净率:'+Stock['pb'][0]+'  每股收益:'+Stock['esp'][0]+ '  每股净资:'+Stock['bvps'][0]+
#                         #     '  每股分配利润:'+Stock['perundp'][0]+'  收入同比:'+Stock['rev'][0]+'%'+'  利润同比:'+Stock['profit'][0]+'%'+'  毛利率:'+Stock['gpr'][0]+'%'+
#                         #     '  净利润率:'+Stock['npr'][0]+'%'), 
#                         #             subtitle_textstyle_opts=opts.TextStyleOpts(color='blue',font_style='italic',font_weight='bold'),
#                         ),
#                         legend_opts=opts.LegendOpts(is_show=False),
#         )
#         .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
#     )
#     return c


