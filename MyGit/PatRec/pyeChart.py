import talib as tb
import tushare as ts
from pyecharts import Line, Kline, Bar, Overlap, Grid


# get Data from tushare
CodeId='000001'
# data = ts.get_k_data(code=CodeId, ktype='D', autype='qfq', index='True')
data = ts.get_k_data(code=CodeId, ktype='D', autype='qfq')

# 数据计算
ADOSC = tb.ADOSC(data.high, data.low, data.close, data.volume, fastperiod=3, slowperiod=11)
AD = tb.AD(data.high, data.low, data.close, data.volume)
ema5 = tb.EMA(data.close, timeperiod=5)
ema21 = tb.EMA(data.close, timeperiod=21)
dif, dea, macd = tb.MACD(data.close, fastperiod=12, slowperiod=26, signalperiod=9)

#数据正规化
ADOs = (ADOSC-ADOSC.mean())/ADOSC.std()
ADs = (AD-AD.mean())/AD.std()
Vol = (data.volume-data.volume.min())/(data.volume.max()-data.volume.min())*3

# 定义k线图的提示框的显示函数
def show_kline_data(params, pos):
    param = params[0]
    if param.data[4]:
      return "date = " + param.name + "<br/>" + "open = " + param.data[1] + "<br/>" + "close = " + param.data[
      2] + "<br/>" + "high = " + param.data[3] + "<br/>" + "low = " + param.data[
      4] + "<br/> "
    else:
      return "date = " + param.name + "<br/>" + "Data = " + param.data[1] + "<br/>"

# 绘制AD
AD_line = Line()
AD_line.add("AD", x_axis=data['date'], y_axis=ADs,
# is_datazoom_show=True,
# #  datazoom_xaxis_index=[0, 1],
# #  is_yaxislabel_align=True,
#  tooltip_tragger='axis',
#  is_toolbox_show=True,
#  legend_top="70%",
#  legend_orient='vertical',
#  legend_pos='right',
#  yaxis_pos='right',
# #  is_xaxislabel_align=True,
#  tooltip_formatter=show_kline_data,
 )

# 绘制ADOSC
ADOSC_line = Line()
ADOSC_line.add("ADO", x_axis=data['date'], y_axis=ADOs, 
 is_datazoom_show=True,
 datazoom_type="both",
#  datazoom_xaxis_index=[0, 1],
 tooltip_tragger='axis',
 is_toolbox_show=True,
 legend_top="70%",
 legend_orient='vertical',
 legend_pos='right',
 yaxis_pos='right',
#  # is_xaxislabel_align=True,
#  tooltip_formatter=show_kline_data,
 )

# 绘制交易量
bar = Bar()
bar.add('vol', data['date'], Vol, is_datazoom_show=True,)

ad_overlap = Overlap(height=600, width=1300)
ad_overlap.add(ADOSC_line)
ad_overlap.add(AD_line)
ad_overlap.add(bar)
ad_overlap.render()

#绘制MACD
dif_line = Line()
dif_line.add("DIF", x_axis=data['date'], y_axis=dif, is_datazoom_show=True,
#  datazoom_xaxis_index=[0, 1],
datazoom_type="both",
 tooltip_tragger='axis',
 is_toolbox_show=True,
 legend_top="70%",
 legend_orient='vertical',
 legend_pos='left',
 yaxis_pos='left',
#  is_yaxislabel_align=True,
 tooltip_formatter=show_kline_data,
 )

dea_line = Line()
dea_line.add("DEA", x_axis=data['date'], y_axis=dea, is_datazoom_show=True,
#  datazoom_xaxis_index=[0, 1],
#  tooltip_tragger='axis',
#  is_toolbox_show=True,
#  legend_top="70%",
#  legend_orient='vertical',
#  legend_pos='left',
#  yaxis_pos='left',
# #  is_xaxislabel_align=True,
#  tooltip_formatter=show_kline_data,
 )

bar = Bar()
bar.add('MACD', data['date'], macd, is_datazoom_show=True)

macd_overlap = Overlap(height=600, width=1300)
macd_overlap.add(dif_line)
macd_overlap.add(dea_line)
macd_overlap.add(bar)
macd_overlap.render()

# 画出K线图
price = [[open, close, lowest, highest] for open, close, lowest, highest in
        zip(data['open'], data['close'], data['low'], data['high'])]
kline = Kline(data['code'][0], title_pos='center')
kline.add('K线', x_axis=data['date'], y_axis=price, is_datazoom_show=True,
  datazoom_type="both",
  mark_point=['min', 'max'],
  datazoom_xaxis_index=[0, 1, 2],
  # is_yaxislabel_align=True,
  # is_xaxislabel_align=True,
  tooltip_tragger='axis',
  yaxis_pos='left',
  legend_top="20%",
  legend_orient='vertical',
  legend_pos='right',
  is_toolbox_show=True,
  tooltip_formatter=show_kline_data)

#绘制EMA5
ema5_line = Line()
ema5_line.add("EMA5", x_axis=data['date'], y_axis=ema5, is_datazoom_show=True,
 datazoom_xaxis_index=[0, 1],
 tooltip_tragger='axis',
 is_toolbox_show=True,
 legend_top="35%",
 legend_orient='vertical',
 legend_pos='right',
 yaxis_pos='left',
#  is_xaxislabel_align=True,
 tooltip_formatter=show_kline_data,
 )

#绘制EMA21
ema21_line = Line()
ema21_line.add("EMA21", x_axis=data['date'], y_axis=ema21, is_datazoom_show=True,
 datazoom_xaxis_index=[0, 1],
 tooltip_tragger='axis',
 is_toolbox_show=True,
 legend_top="35%",
 legend_orient='vertical',
 legend_pos='right',
 yaxis_pos='left',
#  is_xaxislabel_align=True,
 tooltip_formatter=show_kline_data,
 )

#绘制组合图
k_overlap = Overlap(height=600, width=1300)
k_overlap.add(kline)
k_overlap.add(ema5_line)
k_overlap.add(ema21_line)
k_overlap.render()


# 图合并到一张图表中
grid = Grid(height=900, width=1800)
grid.add(k_overlap, grid_bottom="45%")
grid.add(ad_overlap, grid_top='60%')
grid.add(macd_overlap, grid_top='60%')



grid.render('F:/WWWstocks/'+data['code'][0]+'.html')
