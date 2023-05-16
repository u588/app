import pandas as pd
import talib as tb
import shutil
import datetime
from sqlalchemy import create_engine


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxStocks')
engS = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/FindStocks')
today = datetime.date.today().strftime('%m%d')
Today = datetime.datetime.today().strftime('%Y-%m-%d')

df = pd.read_sql('StocksList', eng)[['code','name']]
StocksList = df.code.tolist()
SL = pd.DataFrame(columns=['code'])

for i,Stock in enumerate(StocksList):
    try:
        data = pd.read_sql(Stock, eng).tail(150)
        print(Stock, i, '/', len(StocksList))
        data['ADOSC'] = tb.ADOSC(data.high, data.low, data.close, data.vol, fastperiod=3, slowperiod=11).round(2)
        data['ema5'] = tb.EMA(data.close, timeperiod=5).round(2)
        data['ema21'] = tb.EMA(data.close, timeperiod=21).round(2)
        data['kama55'] = tb.KAMA(data.close, timeperiod=55).round(2)
        data['kama144'] = tb.KAMA(data.close, timeperiod=144).round(2)
        data['ADO'] = ((data.ADOSC-data.ADOSC.mean())/data.ADOSC.std()).round(2)
        d = data.tail(3).set_index('open').reset_index('open')
        dd = d.loc[2]
        d0 = d.loc[0]
        d1 = d.loc[1]
        if dd.ADO>=0 and dd.ema5>dd.ema21>dd.kama55>dd.kama144 and dd.high>=d1.high>=d0.high and dd.close>d1.close>d0.close and dd.low>d1.low>d0.low and dd.close>d1.close>d0.close:
            print('Find'+ Stock)
            SL.loc[i]=Stock
        else:
            pass
        
    except:
        pass
print(' == 找到'+str(SL.shape[0])+'条符合条件记录！==')
SS = pd.merge(df, SL , on='code')
SS['datetime'] = Today
SL.set_index('code').to_csv('/home/ts/FindStocks/'+today+'.txt',header=False)
SS.set_index('datetime').to_sql('FindStocks', engS, if_exists='append')
#shutil.copyfile('E:/Data/'+today+'.txt','Z:/Data/'+today+'.txt')


