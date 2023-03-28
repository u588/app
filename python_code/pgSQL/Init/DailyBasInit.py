from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
#import datetime
import time

home = '10.145.254.55:5432'
job = '10.145.254.56'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/DailyBas')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()


def stockPriceIntraday(ticker):
    intraday = pro.daily_basic(ts_code=ticker,start_date='20181108')
    intraday = intraday.set_index('trade_date')
    intraday.index.name = 'datetime'
    intraday.sort_index(inplace=True)

    intraday.index=pd.DatetimeIndex(intraday.index)
    intraday.index=intraday.index.astype(str)



    pd.io.sql.to_sql(intraday, ticker[:6], eng, if_exists='append')
    print ('intraday for ['+ticker+'] got.')

tickersRawData = pro.stock_basic()
tickers = tickersRawData.ts_code.tolist()




for i, ticker in enumerate(tickers):
    if ticker>'300715':
    	print ('intraday', i, '/', len(tickers))
    	stockPriceIntraday(ticker)
    	#time.sleep(0.2)
    else:
    	pass
#    if i>1:
#      break 
print ('intraday for all stocks got.')
