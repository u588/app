from pyecharts.charts.composite_charts.grid import Grid
from pyecharts.options.global_options import InitOpts
from sqlalchemy import create_engine
import pandas as pd
from pyecharts.components import Table
from pyecharts.charts import Pie, Line
from pyecharts import options as opts
from pyecharts.options import ComponentTitleOpts


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex').connect()
engD = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/StockFina').connect()
engF = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds').connect()

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
        .set_global_opts(xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False),legend_opts=opts.LegendOpts(orient='vertical',pos_right='0%',pos_top='10%',is_show=True),title_opts=opts.TitleOpts(title=StockID, pos_left="center",pos_top="5"),)
    )
    for i, n in enumerate(d.tolist()[1:]):
        c.add_yaxis(d.tolist()[1:][i], d1s[d1s.columns[i+1]].tolist(),is_smooth=True, label_opts=opts.LabelOpts(is_show=False),is_selected=False)
 
    grid_chart = Grid(opts.InitOpts(page_title='分析', width="1350px", height="600px"))

    grid_chart.add(c, grid_opts=opts.GridOpts(border_width=0, pos_left="5%", pos_right="12%"),)

    return grid_chart

