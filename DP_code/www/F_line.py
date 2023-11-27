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

StockID = '000001'
rData = pd.read_sql(StockID, engFn).tail(500).applymap(lambda x : x.replace('-%', '0')).applymap(lambda x : x.replace('%', '')).fillna('0').set_index('date')
r = rData.astype(float)
rData.rename(columns={'vol':'volume','datetime':'date'}, inplace=True)

    

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
# inFlows = ((r['inflow']-r['inflow'].min())/(r['inflow'].max()-r['inflow'].min())*5).round(2)
inFlows = r['inflow']

ADOs = ((ADOSC-ADOSC.mean())/ADOSC.std()).round(2)
ADs = ((AD-AD.mean())/AD.std()).round(2)
Vol = ((data.volume-data.volume.min())/(data.volume.max()-data.volume.min())*3).round(2)

d = np.array(data[['open', 'close']]).tolist()


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


engFn.dispose()