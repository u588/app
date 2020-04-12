import talib as tb
import tushare as ts
import pandas as pd
from pyecharts import Line, Kline, Bar, Overlap, Grid


# get Data
CodeId='002547'
StocksList = pd.read_csv('/home/ts/app/data/StocksList.csv', dtype={'code':object})
Stock = StocksList.loc[StocksList['code']==CodeId].astype(str)
df = Stock
df.reset_index(inplace=True)
data = ts.get_k_data(code=CodeId, ktype='D', autype='qfq')

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

# 定义k线图的提示框的显示函数
def show_kline_data(params, pos):
    param = params[0]
    if param.data[4]:
      return "日期 : " + param.name + "<br/>" + "open : " + param.data[1] + "<br/>" + "high  : " + param.data[
      4] + "<br/>" + "low  : " + param.data[3] + "<br/>" + "close : " + param.data[
      2] + "<br/> "
    else:
      return "日期 : " + param.name + "<br/>" + "数值 : " + param.data[1] + "<br/>"


# 绘制ADOSC
ADOSC_line = Line()
ADOSC_line.add("ADO", x_axis=data['date'], y_axis=ADOs, is_datazoom_show=True,
 tooltip_tragger='axis',
 is_toolbox_show=True,
 legend_top="70%",
 legend_orient='vertical',
 legend_pos='right',
 yaxis_pos='right',
 tooltip_formatter=show_kline_data,
 )

# 绘制AD
AD_line = Line()
AD_line.add("AD", x_axis=data['date'], y_axis=ADs)

# 绘制交易量
bar = Bar()
bar.add('vol', data['date'], Vol, is_datazoom_show=True)

ad_overlap = Overlap(height=600, width=1300)
ad_overlap.add(ADOSC_line)
ad_overlap.add(AD_line)
ad_overlap.add(bar)
ad_overlap.render()

#绘制MACD
dif_line = Line()
dif_line.add("DIF", x_axis=data['date'], y_axis=dif, is_datazoom_show=True,
 tooltip_tragger='axis',
 is_toolbox_show=True,
 legend_top="70%",
 legend_orient='vertical',
 legend_pos='left',
 yaxis_pos='left',
 tooltip_formatter=show_kline_data,
 )


dea_line = Line()
dea_line.add("DEA", x_axis=data['date'], y_axis=dea)



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
kline = Kline(subtitle_color =  '#008', subtitle_text_size=12, subtitle=
  ('所属行业: '+Stock['industry']+'  地域: '+Stock['area']+'  市盈率: '+Stock['pe']+'  总股本: '+Stock['totals']+'亿元'+
    '  流通股本: '+Stock['outstanding']+'亿元'+'  市净率:'+Stock['pb']+'  每股收益:'+Stock['esp']+'  每股净资:'+Stock['bvps']+
    '  每股分配利润:'+Stock['perundp']+'  收入同比:'+Stock['rev']+'%'+'  利润同比:'+Stock['profit']+'%'+'  毛利率:'+Stock['gpr']+'%'+
    '  净利润率:'+Stock['npr']+'%'
    ),
  title_pos='center')
kline.add('K线', x_axis=data['date'], y_axis=price, is_datazoom_show=True,
  mark_point=['min', 'max'], mark_point_valuedim =['lowest', 'highest'] ,
  # mark_line=
  datazoom_xaxis_index=[0,1,2],
  datazoom_type = 'both',
  datazoom_range = [80, 100],
  # is_xaxislabel_align=True,
  # is_yaxislabel_align=True,
  tooltip_tragger='axis',
  yaxis_pos='left',
  legend_top="20%",
  legend_orient='vertical',
  legend_pos='right',
  # legend_text_size=12,
  # legend_text_color='b',
  is_toolbox_show=True,
  tooltip_formatter=show_kline_data)

#绘制EMA5
ema5_line = Line()
ema5_line.add("EMA5", x_axis=data['date'], y_axis=ema5)

#绘制MaEMA5
maema5_line = Line()
maema5_line.add("MaEMA5", x_axis=data['date'], y_axis=maema5)

#绘制EMA21
ema21_line = Line()
ema21_line.add("EMA21", x_axis=data['date'], y_axis=ema21)

#绘制EMA55
kama55_line = Line()
kama55_line.add("KAMA55", x_axis=data['date'], y_axis=kama55)

#绘制组合图
k_overlap = Overlap(height=600, width=1300)
k_overlap.add(kline)
k_overlap.add(ema5_line)
k_overlap.add(maema5_line)
k_overlap.add(ema21_line)
k_overlap.add(kama55_line)
k_overlap.render()


# 图合并到一张图表中
grid = Grid(height=600, width=1300, page_title=(df['code'][0]+'：'+df['name'][0]))
grid.add(k_overlap, grid_bottom="45%")
grid.add(macd_overlap, grid_top='60%')
grid.add(ad_overlap, grid_top='60%')


grid.render('/home/ts/app/www/html/'+data['code'][0]+df['name'][0]+'.html')
print('ok')
