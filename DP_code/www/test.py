import talib as tb
import tushare as ts
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from pyecharts import options as opts
from pyecharts.globals import ThemeType
from pyecharts.commons.utils import JsCode
from pyecharts.charts import Kline, Line, Bar, Grid

engFn = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds')


def iBar(StockID):

    rData = pd.read_sql(StockID, engFn).tail(500).applymap(lambda x : x.replace('-%', '0')).applymap(lambda x : x.replace('%', '')).fillna('0').set_index('date')
    engFn.dispose()
    r = rData.astype(float).reset_index()

    ema3 = tb.EMA(r.inflow, timeperiod=3)
    ema5 = tb.EMA(r.inflow, timeperiod=5)
    ema21 = tb.EMA(r.inflow, timeperiod=21)

    c = (
        Bar()
        .add_xaxis(xaxis_data=r.date.tolist())
        .add_yaxis(
            series_name="inFlow",
            y_axis=r.inflow.tolist(),
            # xaxis_index=2,
            # yaxis_index=2,
            label_opts=opts.LabelOpts(is_show=False),
            itemstyle_opts=opts.ItemStyleOpts(
                color=JsCode(
                    """
                    function(params) {
                        var colorList;
                        if (params.data >= 0) {
                        colorList = 'red';
                        } else {
                        colorList = 'green';
                        }
                        return colorList;
                    }
                    """
                )
            ),
        )
        .set_global_opts(
            xaxis_opts=opts.AxisOpts(
                type_="category",
                # grid_index=2,
                axislabel_opts=opts.LabelOpts(is_show=False),
            ),
            yaxis_opts=opts.AxisOpts(
                # grid_index=2,
                split_number=4,
                axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                axistick_opts=opts.AxisTickOpts(is_show=False),
                splitline_opts=opts.SplitLineOpts(is_show=False),
                axislabel_opts=opts.LabelOpts(is_show=True),
            ),
            legend_opts=opts.LegendOpts(pos_top='95%',is_show=True),
        )
    )

    kline_line = (
    Line()
    .add_xaxis(xaxis_data=r.date.tolist())
    .add_yaxis(
        series_name="EMA3",
        y_axis=ema3,
        xaxis_index=2,
        yaxis_index=2,
        is_smooth=True,
        linestyle_opts=opts.LineStyleOpts(opacity=0.5),
        label_opts=opts.LabelOpts(is_show=False),
    )
    .add_yaxis(
        series_name="EMA5",
        y_axis=ema5,
        xaxis_index=2,
        yaxis_index=2,
        is_smooth=True,
        linestyle_opts=opts.LineStyleOpts(opacity=0.5),
        label_opts=opts.LabelOpts(is_show=False),
    )
    .add_yaxis(
        series_name="EMA21",
        y_axis=ema21,
        xaxis_index=2,
        yaxis_index=2,
        is_smooth=True,
        linestyle_opts=opts.LineStyleOpts(opacity=1,width=2),
        label_opts=opts.LabelOpts(is_show=False),
    )
    .set_global_opts(
        xaxis_opts=opts.AxisOpts(
            type_="category",
            grid_index=1,
            axislabel_opts=opts.LabelOpts(is_show=False),
        ),
        yaxis_opts=opts.AxisOpts(
            grid_index=1,
            split_number=3,
            axisline_opts=opts.AxisLineOpts(is_on_zero=False),
            axistick_opts=opts.AxisTickOpts(is_show=False),
            splitline_opts=opts.SplitLineOpts(is_show=False),
            axislabel_opts=opts.LabelOpts(is_show=True),
        ),
    )
    )

    overlap_Bar = c.overlap(kline_line)

    return overlap_Bar


def sBar(StockID) -> Bar:

    rData = pd.read_sql(StockID, engFn).tail(500).applymap(lambda x : x.replace('-%', '0')).applymap(lambda x : x.replace('%', '')).fillna('0').set_index('date')
    engFn.dispose()
    r = rData.astype(float).reset_index()

    n = ['bEqu', 'mEqu', 'sEqu']
    c = (
        Bar()
        .add_xaxis(r.date.tolist())
        .set_global_opts(title_opts=opts.TitleOpts(title=""),)
    )

    for j in n:
        c.add_yaxis(
            series_name=j, 
            y_axis=r[j].tolist(),
            stack='大中小单',
            label_opts=opts.LabelOpts(is_show=False),

        )   

    return c

def test(StockID):

    grid_chart = Grid(opts.InitOpts(js_host='/',page_title=StockID, width="1400px", height="600px"))
    grid_chart.add(sBar(StockID), grid_opts=opts.GridOpts(pos_left="5%", pos_right="2%", pos_top="6%",height="55%"), )    
    grid_chart.add(iBar(StockID), grid_opts=opts.GridOpts(pos_left="5%", pos_right="2%", pos_top="65%",height="30%"), )    

    return grid_chart

