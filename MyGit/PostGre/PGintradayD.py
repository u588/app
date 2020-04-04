from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
# import datetime
# import os
# import time


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/db')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

def stockPriceIntraday(ticker):
    intraday = pro.daily(ts_code=ticker)
    intraday = intraday.set_index('trade_date')
    intraday.index.name = 'timestamp'
    intraday.sort_index(inplace=True)
    intraday.reset_index(inplace=True)
 #   print(intraday).head()
    if pd.io.sql.has_table(ticker, eng):
        history = pd.read_sql(ticker, eng)
        stamp = history.tail(1)['timestamp'].tolist()[0]
        intraday = intraday[(intraday['timestamp']>stamp)]
    intraday.set_index(['timestamp'], inplace=True)
    pd.io.sql.to_sql(intraday, ticker, eng, if_exists='append')
#    print ('intraday for ['+ticker+'] got.')

tickersRawData = pro.stock_basic()
tickers = tickersRawData.loc[:, ['ts_code']].ts_code.tolist()

#dateToday = datetime.datetime.today().strftime('%Y%m%d')
# file = 'F:/QutData/TickersList_'+dateToday+'.csv'
# tickersRawData.to_csv(file)
# print ('Tickers saved')



for i, ticker in enumerate(tickers):
    try:
    	print ('intraday', i, '/', len(tickers))
    	stockPriceIntraday(ticker)
    	time.sleep(0.2)
    except:
    	pass
#    if i>1:
#       break 
print ('intraday for all stocks got.')
