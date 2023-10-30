from pyecharts.charts.composite_charts.grid import Grid
from sqlalchemy import create_engine
import pandas as pd
from pyecharts.charts import Line
from pyecharts import options as opts



eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')
engD = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxFS')
engF = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds')

def line(StockID) -> Line:
    Data = pd.read_sql(StockID, engD)
    # ll = list(Data.columns[0:10])+['col17','col21','col22','col27','col33','col35','col36','col40','col54','col63','col81','col83','col86','col92','col95','col131','col135','col143'] + \
        # list(Data.columns[159:190])+['col191']+list(Data.columns[193:230])+['col238','col239','col243','col244','col284','col326','col242','col246','col401','col502','col506','col509','col519','col520','col580','col581']
    dn = pd.read_sql('tdxFSLists', engD)
    ll =  dn.Code.to_list()
    Data = Data[ll]
    
    dd = Data.set_index('report_date')
    d = list(dd.columns)
    dd.reset_index(inplace=True)
    d1s = dd
    date = dd.report_date.apply(str).to_list()
    c = (
        Line(opts.InitOpts(page_title='财务分析',width="1330px", height="600px"))
        .add_xaxis(date)
        .set_global_opts(
            # tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False), 
            legend_opts=opts.LegendOpts(type_='scroll',orient='horizontal',pos_left='5%',pos_bottom='0%',is_show=True),
            title_opts=opts.TitleOpts(title=StockID, pos_left="center",pos_top="5"),
            datazoom_opts=[
                opts.DataZoomOpts(xaxis_index=[0, 0],is_show=False, type_="inside",range_start=0, range_end=100),
                opts.DataZoomOpts(xaxis_index=[0, 1],is_show=True, range_start=0, range_end=100,pos_bottom='6%'),
            ],

            )
        )
    for i in d:
        try:
            c.add_yaxis(
                series_name=dn[(dn.Code==i)].cnName.tolist()[0], 
                y_axis=d1s[i].tolist(),
                is_smooth=True,
                is_selected=False,
                # is_hover_animation=True,
                label_opts=opts.LabelOpts( is_show=False),
            )
        except:
            pass
    grid_chart = Grid(opts.InitOpts(page_title='分析', width="1360px", height="650px"))

    grid_chart.add(c, grid_opts=opts.GridOpts(border_width=0, pos_left="8%", pos_right="5%",pos_bottom="15%"),)

    return grid_chart

