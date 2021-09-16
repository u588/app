import talib as tb
import tushare as ts
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')
engF = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/StockFina')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/StockBas')

from pyecharts import options as opts
from pyecharts.globals import ThemeType
from pyecharts.commons.utils import JsCode
from pyecharts.charts import Kline, Line, Bar, Grid


# get Data
def Kchart(CodeId):

    # StocksList = pd.read_csv('/home/ts/app/data/StocksList.csv', dtype={'code':object})
    StocksList = pd.read_sql('StocksDetail', engB)
    St = StocksList.loc[StocksList['code']==CodeId]
    Stock = St.fillna('--')
    StF = pd.read_sql(CodeId, engF).tail(1)
    StockF = StF.fillna('----')
    df = Stock
    df.reset_index(inplace=True)
    data= pd.read_sql(CodeId, eng).tail(500)
    data.rename(columns={'vol':'volume','datetime':'date'}, inplace=True)
    data.date = data.date.str.replace(' 15:00','')
    # data = ts.get_k_data(code=CodeId, ktype='D', autype='qfq').tail(250)
      

    # 数据计算
    ADOSC = tb.ADOSC(data.high, data.low, data.close, data.volume, fastperiod=5, slowperiod=21)
    AD = tb.AD(data.high, data.low, data.close, data.volume)
    ema5 = tb.EMA(data.close, timeperiod=5).round(2)
    maema5 = tb.EMA(ema5, timeperiod=5).round(2)
    ema21 = tb.EMA(data.close, timeperiod=21).round(2)
    kama55 = tb.KAMA(data.close, timeperiod=55).round(2)
    dif, dea, macd = tb.MACD(data.close, fastperiod=8, slowperiod=21, signalperiod=5)
    dif=dif.round(2)
    dea=dea.round(2)
    macd=macd.round(2)


    #数据正规化
    ADOs = ((ADOSC-ADOSC.mean())/ADOSC.std()).round(2)
    ADs = ((AD-AD.mean())/AD.std()).round(2)
    Vol = ((data.volume-data.volume.min())/(data.volume.max()-data.volume.min())*3).round(2)
 
    d = np.array(data[['open', 'close']]).tolist()

    # 绘制ADOSC
    ADOSC_line = (
            Line()
            .add_xaxis(xaxis_data=data.date.tolist())
            .add_yaxis(
                series_name="ADOs",
                y_axis=ADOs,
                xaxis_index=2,
                yaxis_index=2,
                label_opts=opts.LabelOpts(is_show=False),
            )
            .add_yaxis(
                series_name="AD",
                y_axis=ADs,
                xaxis_index=2,
                yaxis_index=2,
                label_opts=opts.LabelOpts(is_show=False),
            )
            .set_global_opts(legend_opts=opts.LegendOpts(is_show=False))
    )

    Vol_bar = (
            Bar()
            .add_xaxis(xaxis_data=data.date.tolist())
            .add_yaxis(
                series_name="Volumn",
                y_axis=Vol.tolist(),
                xaxis_index=2,
                yaxis_index=2,
                label_opts=opts.LabelOpts(is_show=False),
                itemstyle_opts=opts.ItemStyleOpts(
                color=JsCode(

                    """
                function(params) {
                    var colorList;
                    if (barData[params.dataIndex][1] > barData[params.dataIndex][0]) {
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
                    grid_index=2,
                    axislabel_opts=opts.LabelOpts(is_show=False),
                ),
                yaxis_opts=opts.AxisOpts(
                    grid_index=2,
                    split_number=4,
                    axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                    axistick_opts=opts.AxisTickOpts(is_show=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                    axislabel_opts=opts.LabelOpts(is_show=True),
                ),
                legend_opts=opts.LegendOpts(pos_top='69%',is_show=True),
            )
        )

    Overlap_ADOSC_Vol = Vol_bar.overlap(ADOSC_line)


    #绘制MACD
    DIF_line = (
            Line()
            .add_xaxis(xaxis_data=data.date.tolist())
            .add_yaxis(
                series_name="DIF",
                y_axis=dif,
                xaxis_index=2,
                yaxis_index=2,
                label_opts=opts.LabelOpts(is_show=False),
            )
            .add_yaxis(
                series_name="DEA",
                y_axis=dea,
                xaxis_index=2,
                yaxis_index=2,
                label_opts=opts.LabelOpts(is_show=False),
            )
            .set_global_opts(legend_opts=opts.LegendOpts(is_show=False))
    )

    MACD_bar = (
            Bar()
            .add_xaxis(xaxis_data=data.date.tolist())
            .add_yaxis(
                series_name="MACD",
                y_axis=macd.tolist(),
                xaxis_index=2,
                yaxis_index=2,
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
                    grid_index=2,
                    axislabel_opts=opts.LabelOpts(is_show=False),
                ),
                yaxis_opts=opts.AxisOpts(
                    grid_index=2,
                    split_number=4,
                    axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                    axistick_opts=opts.AxisTickOpts(is_show=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                    axislabel_opts=opts.LabelOpts(is_show=True),
                ),
                legend_opts=opts.LegendOpts(pos_top='95%',is_show=True),
            )
        )

    Overlap_MACD_DIF = MACD_bar.overlap(DIF_line)


    # 画出K线图
    kline = (
            Kline()
            .add_xaxis(xaxis_data=data.date.tolist())
            .add_yaxis(
                series_name="K线",
                y_axis=np.array(data[['open', 'close','low', 'high']]).tolist(),
                itemstyle_opts=opts.ItemStyleOpts(
                    color="#ef232a",
                    color0="#14b143",
                    border_color="#ef232a",
                    border_color0="#14b143",
                ),
                markpoint_opts=opts.MarkPointOpts(
                    data=[
                        opts.MarkPointItem(type_="max", name="最大值"),
                        opts.MarkPointItem(type_="min", name="最小值"),
                    ]
                ),
            )
            .set_global_opts(
                legend_opts=opts.LegendOpts(pos_top='10%',is_show=True),
                title_opts=opts.TitleOpts(
                    title=(CodeId+' : '+Stock.name[0]), pos_left="center",
                    subtitle=(StockF['date'].tolist()[0]+
                            '  所属行业: '+Stock['icLev1'].tolist()[0]+'、'+Stock['icLev3'].tolist()[0]+  '    地域: '+Stock['regi'].tolist()[0]+'    控股股东: '+Stock['cSH'].tolist()[0]+' '+Stock['cSHr'].tolist()[0]+
                            '    最终控住人: '+Stock['ucSH'].tolist()[0]+' '+Stock['ucSHr'].tolist()[0]+'    注册资本: '+Stock['regCap'].tolist()[0]+ '    雇员人数：'+Stock['empNum'].tolist()[0] +"\n" + "\n"+
                            '收益: '+StockF['eps'].tolist()[0]+'  净资: '+StockF['bps'].tolist()[0]+'  资本公积金: '+StockF['capital_rese_ps'].tolist()[0]+'  未分利润 :'+StockF['undist_profit_ps'].tolist()[0]+'  经营现金流: '+StockF['ocfps'].tolist()[0]+
                            '  总收入: '+str(round(float(StockF['totalRevenue'].tolist()[0])/100000000, 2))+'亿元'+'  总收入同比: '+StockF['tr_yoy'].tolist()[0]+
                            '  净利润: '+str(round(float(StockF['nProfit'].tolist()[0])/100000000, 2))+'亿元'+'  净利润同比: '+StockF['nProfit_yoy'].tolist()[0]+
                            '  毛利率: '+StockF['gProfit_margin'].tolist()[0]+'  净利率: '+StockF['nProfit_margin'].tolist()[0]+'  净资收益率: '+StockF['roe'].tolist()[0]+'  产权比: '+StockF['debt_to_eqt'].tolist()[0]+'  资产负债率: '+StockF['debt_to_assets'].tolist()[0]), 
                    subtitle_textstyle_opts=opts.TextStyleOpts(color='blue',font_style='italic',font_weight='bold')
                ),
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    is_scale=True,
                    boundary_gap=False,
                    axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                    split_number=20,
                    min_="dataMin",
                    max_="dataMax",
                ),
                yaxis_opts=opts.AxisOpts(
                    is_scale=True, 
                    splitline_opts=opts.SplitLineOpts(is_show=True)
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="line"),
                datazoom_opts=[
                    opts.DataZoomOpts(
                        is_show=False, type_="inside", xaxis_index=[0, 0], range_end=100
                    ),
                    opts.DataZoomOpts(
                        is_show=True, xaxis_index=[0, 1], pos_top="97%", range_end=100
                    ),
                    opts.DataZoomOpts(is_show=False, xaxis_index=[0, 2], range_end=100),
                ],
                # 三个图的 axis 连在一块
                # axispointer_opts=opts.AxisPointerOpts(
                # is_show=True,
                # link=[{"xAxisIndex": "all"}],
                # label=opts.LabelOpts(background_color="#777"),
                # ),
            )
    )

    kline_line = (
        Line()
        .add_xaxis(xaxis_data=data.date.tolist())
        .add_yaxis(
            series_name="MA5",
            y_axis=ema5,
            xaxis_index=2,
            yaxis_index=2,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(opacity=0.5),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            series_name="MaEMA5",
            y_axis=maema5,
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
        .add_yaxis(
            series_name="KAMA55",
            y_axis=kama55,
            xaxis_index=2,
            yaxis_index=2,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(opacity=0.2,width=16),
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

    overlap_kline_line = kline.overlap(kline_line)


    # 图合并到一张图表中
    grid_chart = Grid(opts.InitOpts(js_host='/',page_title=Stock.name[0], width="1500px", height="900px"))

     # demo 中的代码也是用全局变量传的
    grid_chart.add_js_funcs("var barData = {}".format(d))

    # K线图和 MA5 的折线图
    grid_chart.add(
    overlap_kline_line,
    grid_opts=opts.GridOpts(pos_left="3%", pos_right="1%", pos_top="8%",height="58%"),
    )

    # Volumn 柱状图
    grid_chart.add(
    Overlap_ADOSC_Vol,
    grid_opts=opts.GridOpts(
        pos_left="3%", pos_right="1%", pos_top="71%", height="10%"
    ),
    )

    # MACD DIFS DEAS
    grid_chart.add(
    Overlap_MACD_DIF,
    grid_opts=opts.GridOpts(
        pos_left="3%", pos_right="1%", pos_top="82%", height="12%"
    ),
    )
    return grid_chart


def Kdata(CodeId):
    # CodeId='603530'
    name = CodeId
    StocksList = pd.read_csv('/home/ts/app/data/StocksList.csv', dtype={'code':object})
    Stock = StocksList.loc[StocksList['code']==CodeId].astype(str)
    df = Stock
    df.reset_index(inplace=True)
    data = ts.get_k_data(code=CodeId, ktype='D', autype='qfq').tail(250)
    d = data[['open','close']].to_json(orient='values')
  
    return d