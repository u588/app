import pandas as pd
import mpl_finance as mpf
import matplotlib.pylab as plt
import talib as tb
import tushare as ts

import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
import matplotlib as mpl
from matplotlib.pylab import date2num
import seaborn as sns
from sqlalchemy import create_engine
import matplotlib.ticker as ticker

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

engI = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs')
engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')

pro = ts.pro_api()



mpl.rcParams['font.sans-serif'] = ['KaiTi'] # 指定默认字体
mpl.rcParams['axes.unicode_minus'] = False # 解决保存图像是负号'-'显示为方块的问题
plt.style.use({'figure.figsize':(18, 9)})

ob='002384.SZ'

DataSet = pro.daily(ts_code=ob).head(20)
DataSet.dropna(inplace=True)
DataSet.set_index('trade_date', inplace=True)
DataSet.sort_index(ascending=1, inplace=True)
DataSet.index = pd.DatetimeIndex(DataSet.index)
DataSet['std'] = DataSet[['open', 'high', 'low', 'close']].std(axis=1)
DataSet['skew'] = DataSet[['open', 'high', 'low', 'close']].skew(axis=1)
DataSet['kurt'] = DataSet[['open', 'high', 'low', 'close']].kurt(axis=1)

df = DataSet
df['ADOSC'] = tb.ADOSC(df.high, df.low, df.close, df.vol, fastperiod=3, slowperiod=11)
df['AD'] = tb.AD(df.high, df.low, df.close, df.vol)

plt.figure()

ax = plt.subplot2grid((20,1),(12,0),rowspan=8,colspan=1)


#设置x轴主刻度格式
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.xaxis.grid(True, which='major')
ax.yaxis.grid(True)
# ax.xaxis.set_xticks(rotation=45)

#设置x副刻度格式
ax.xaxis.set_minor_formatter(mdates.DateFormatter('%m'))
ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
ax.xaxis.grid(True, which='minor', ls='--', lw=0.5 , alpha=0.8)


# ax.yaxis.set_minor_locator()

# 设置y轴主刻度格式	
ax.yaxis.set_major_formatter(FormatStrFormatter('%.0f'))
# ax.yaxis.set_major_locator(MultipleLocator(500))
#设置y副刻度格式
ax.yaxis.set_minor_formatter(FormatStrFormatter('%.0f'))
# ax.yaxis.set_minor_locator(MultipleLocator(500))
ax.yaxis.grid(True, which='minor')

#参数pad用于设置刻度线与标签间的距离


# plt.subplots(2,1,1, sharex=True)
plt.setp(ax.get_xticklabels(which='major'), fontsize=8)
plt.setp(ax.get_xticklabels(which='minor'), fontsize=6)

# ax.plot(DataSet.index, DataSet.close)

ax1= plt.subplot2grid((20,1), (0,0), rowspan=11, colspan=1)
plt.title(ob)
# ax1.xaxis.set_major_locator(mdates.YearLocator())
# ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
# ax1.xaxis.grid(True, which='minor', ls='--', lw=0.5 , alpha=0.8)
# ax1.tick_params(pad=5)
# ax1.tick_params(which='minor', labelsize=8)

# plt.setp(ax.get_xticklabels(), visible=False)
# plt.setp(ax.get_xticklabels(which='minor'), visible=False)
# plt.setp(ax.get_xticklines(), visible=False)

# ax1.spines['right'].set_visible(False)
# ax1.spines['left'].set_visible(False)
# ax.spines['bottom'].set_visible(False)
# ax.tick_params(color='none')
# ax.xaxis.set_major_locator(ticker.NullLocator())
# plt.setp(ax1, xticklabels=[])
# ax1.set_xticks([])
# ax1.set_yticks([])


mpf.candlestick2_ohlc(ax1,DataSet.open, DataSet.high, DataSet.low, DataSet.close,width=0.3,colorup='r',colordown='g', alpha=0.7)
df.close.plot(ax=ax)
# plt.bar(DataSet.index, DataSet.vol)
# DataSet[['skew', 'kurt']].plot(ax=ax1)
# tb.AD(df.high, df.low, df.close, df.vol).plot(ax=ax)

# DataSet.plot(subplots=True, layout=(2,1),title=b, kind='line', style='-', ax=ax, grid=True, figsize=(18, 9), colormap='tab10' , sort_columns=True, linewidth=1 )
# DataSet.close.plot(title=b, kind='line', style='-', ax=ax, grid=True, figsize=(18, 9), colormap='tab10' , sort_columns=True, linewidth=1 )
# DataSet.vol.plot(title=b, kind='hist', ax=ax, figsize=(18, 9), colormap='tab10' )
# plt.xticks([])
# plt.yticks([])
# plt.grid(True)
# plt.subplots_adjust(left=0.03 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
	
# b ='i000001'
# Plot(b)
# plt.xlim('1996-01-01', '2019-01-01')
# plt.savefig('f:/Plot/' + b + '.png', dpi=350)
plt.show()
