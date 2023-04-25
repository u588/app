import pandas as pd
import talib as tb
import tushare as ts

CodeId = '002384'
data = ts.get_k_data(code=CodeId, ktype='D', autype='qfq')

data['pre_close']=data.close.shift(1)
ADOSC = tb.ADOSC(data.high, data.low, data.close, data.volume, fastperiod=5, slowperiod=21)
data['pc_chg']=(((data.close-data.pre_close)/data.pre_close)*100).round(0)
data['open_chg']=(((data.open-data.pre_close)/data.pre_close)*100).round(0)
data['day_chg']=(((data.close-data.open)/data.open)*100).round(0)
data.loc[abs(data.pc_chg)>11, 'pc_chg']=0.0
data.loc[abs(data.open_chg)>11, 'open_chg']=0.0

data['ADOSC'] = ((ADOSC-ADOSC.mean())/ADOSC.std()).round(2)

data['ema5'] = tb.EMA(data.close, timeperiod=5).round(2)
data['ema8'] = tb.EMA(data.close, timeperiod=8).round(2)
data['ema21'] = tb.EMA(data.close, timeperiod=21).round(2)
data['kama55'] = tb.KAMA(data.close, timeperiod=55).round(2)

data['sum3']=tb.SUM(data.pc_chg, timeperiod=3).round(1)
data['sum5']=tb.SUM(data.pc_chg, timeperiod=5).round(1)
data['sum8']=tb.SUM(data.pc_chg, timeperiod=8).round(1)
data['sum13']=tb.SUM(data.pc_chg, timeperiod=13).round(1)
data['sum21']=tb.SUM(data.pc_chg, timeperiod=21).round(1)
data['sum34']=tb.SUM(data.pc_chg, timeperiod=34).round(1)
data['sum55']=tb.SUM(data.pc_chg, timeperiod=55).round(1)
data['sum89']=tb.SUM(data.pc_chg, timeperiod=89).round(1)
data['sum144']=tb.SUM(data.pc_chg, timeperiod=144).round(1)
data['sum233']=tb.SUM(data.pc_chg, timeperiod=233).round(1)

data.to_csv('f:/StocksData/'+CodeId+'.csv')

