from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
#import datetime
import time

home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = home

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/DailyBas')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()


def stockPriceIntraday(ticker):
    i1 = pro.daily_basic(ts_code=ticker,end_date='20020611')
    i1 = i1.set_index('trade_date')
    i1.index.name = 'datetime'
    i1.sort_index(inplace=True)

    i2 = pro.daily_basic(ts_code=ticker,start_date='20020612')
    i2 = i2.set_index('trade_date')
    i2.index.name = 'datetime'
    i2.sort_index(inplace=True)

    intraday= pd.concat([i1,i2], axis=0)
    intraday.index=pd.DatetimeIndex(intraday.index)
    intraday.index=intraday.index.astype(str)



    pd.io.sql.to_sql(intraday, ticker[:6], eng, if_exists='replace')
    print ('intraday for ['+ticker+'] got.')

tickersRawData = pro.stock_basic()
tickers = tickersRawData.ts_code.tolist()




for i, ticker in enumerate(tickers):
    try:
    	print ('intraday', i, '/', len(tickers))
    	stockPriceIntraday(ticker)
    	time.sleep(0.2)
    except:
    	pass
#    if i>1:
#      break 
print ('intraday for all stocks got.')
