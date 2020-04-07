from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
import datetime
import time


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/DailyBasD')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

dateToday = datetime.datetime.today().strftime('%Y%m%d')
tradeDates = pd.date_range('20180101', dateToday).strftime('%Y%m%d').tolist()

for i, tradeDate in enumerate(tradeDates):
    try:
        print ('intraday', i, '/', len(tradeDates))
        Bas = pd.read_sql(tradeDate, eng)
        Bas.set_index(['trade_date'], inplace=True)
        Bas.index.name = 'datetime'
        Bas.sort_index(inplace=True)
        Bas.index = pd.DatetimeIndex(Bas.index)
        Bas.index = Bas.index.astype(str)
        pd.io.sql.to_sql(Bas, tradeDate, eng, if_exists='replace')
        print ('intraday for ['+tradeDate+'] got.')
        time.sleep(0.2)
    except:
        pass
#    if i>0:
#      break
print ('daily_basic for all stocks got.')
