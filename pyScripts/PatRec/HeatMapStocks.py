import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib as mpl
import data_fq  as fq
from sqlalchemy import create_engine
import talib as tb
import tushare as ts

engS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engX = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxXdXr')

StockCode = '002639'

D = pd.read_sql(StockCode, engS)
Data = D[D.datetime>'2000-01-01']
X = pd.read_sql(StockCode, engX)
XdXr = X[X.year>1999]

# Data = pd.read_sql(StockCode, engS)
# XdXr = pd.read_sql(StockCode, engX)
data = fq.qfq(Data, XdXr)[['open', 'high', 'low', 'close', 'vol']].tail(-10).reset_index()
# data = ts.get_k_data(code=CodeId, ktype='D', autype='qfq')

data['pre_close']=data.close.shift(1)
# ADOSC = tb.ADOSC(data.high, data.low, data.close, data.volume, fastperiod=5, slowperiod=21)
data['pc_chg']=(((data.close-data.pre_close)/data.pre_close)*100).round(1)
data['open_chg']=(((data.open-data.pre_close)/data.pre_close)*100).round(1)
data['day_chg']=(((data.close-data.open)/data.open)*100).round(1)
data['day_H'] = (((data.high-data.open)/data.open)*100).round(1)
data['day_L'] = (((data.low-data.open)/data.open)*100).round(1)
# data.loc[abs(data.pc_chg)>11, 'pc_chg']=0.0
# data.loc[abs(data.open_chg)>11, 'open_chg']=0.0

# data['ADOSC'] = ((ADOSC-ADOSC.mean())/ADOSC.std()).round(2)

# data['ema5'] = tb.EMA(data.close, timeperiod=5).round(2)
# data['ema8'] = tb.EMA(data.close, timeperiod=8).round(2)
# data['ema21'] = tb.EMA(data.close, timeperiod=21).round(2)
# data['kama55'] = tb.KAMA(data.close, timeperiod=55).round(2)

# data['sum3']=tb.SUM(data.pc_chg, timeperiod=3).round(1)
# data['sum5']=tb.SUM(data.pc_chg, timeperiod=5).round(1)
# data['sum8']=tb.SUM(data.pc_chg, timeperiod=8).round(1)
# data['sum13']=tb.SUM(data.pc_chg, timeperiod=13).round(1)
# data['sum21']=tb.SUM(data.pc_chg, timeperiod=21).round(1)
# data['sum34']=tb.SUM(data.pc_chg, timeperiod=34).round(1)
# data['sum55']=tb.SUM(data.pc_chg, timeperiod=55).round(1)
# data['sum89']=tb.SUM(data.pc_chg, timeperiod=89).round(1)
# data['sum144']=tb.SUM(data.pc_chg, timeperiod=144).round(1)
# data['sum233']=tb.SUM(data.pc_chg, timeperiod=233).round(1)


mpl.rcParams['font.sans-serif'] = ['KaiTi']

df = data
dd = df[['open_chg', 'day_chg', 'close']].groupby(['day_chg', 'open_chg']).count().reset_index()
dh = df[['open_chg', 'day_H', 'close']].groupby(['day_H', 'open_chg']).count().reset_index()
dl = df[['open_chg', 'day_L', 'close']].groupby(['day_L', 'open_chg']).count().reset_index()

# dd.to_csv('f:/group.csv')
# data = dd.set_index('open_chg')

pt = dd.pivot(index='open_chg', columns='day_chg', values='close')
pH = dh.pivot(index='open_chg', columns='day_H', values='close')
pL = dl.pivot(index='open_chg', columns='day_L', values='close')
# pt = dd.pivot(index='open_round', columns='day_round', values='close')
f, ax = plt.subplots(figsize = (16,9))
# cmap = sns.cubehelix_palette(start = 1, rot = 3, gamma=0.8, as_cmap = True)  
# 
# 
# 
# 
# 
sns.lmplot('open_chg','day_chg',data,hue=None, fit_reg=False)
# sns.heatmap(pL, cmap = 'cool',linewidths=0.1, linecolor=(0.1, 0.2, 0.5, 0.05))   
# ax.set_title(StockCode)
# ax.set_xlabel('day_chg')
# ax.set_ylabel('open_chg')

plt.show()