import pandas as pd
import talib as tb
import datetime
from sqlalchemy import create_engine


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/tdxStocks')
today = datetime.date.today().strftime('%m%d')

df = pd.read_csv('f:/WWWstocks/StocksList.csv', dtype={'code':object})
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
# SL.set_index('code').to_csv('e:/' + today +'.txt',header=False)
SL.set_index('code').to_csv('f:/' + today +'.txt', header=False)
# shutil.copyfile('E:/FindStocks.txt','Z:/Data/FindStocks.txt')
