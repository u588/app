from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
#import datetime
#import os
#import time


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/db')

def stockPriceIntraday(ticker):
    intraday = ts.get_hist_data(ticker, ktype='5')
    intraday.sort_index(inplace=True)
    intraday.index.name = 'timestamp'
    intraday.reset_index(inplace=True)
    if pd.io.sql.has_table(ticker, eng):
        history = pd.read_sql(ticker, eng)
        stamp = history.tail(1)['timestamp'].tolist()[0]
        intraday = intraday[(intraday['timestamp']>stamp)]
    intraday.set_index(['timestamp'], inplace=True) 
    pd.io.sql.to_sql(intraday, ticker, eng, if_exists='append')
    print ('intraday for ['+ticker+'] got.')

tickersRawData = ts.get_stock_basics()
tickers = tickersRawData.index.tolist()
#dateToday = datetime.datetime.today().strftime('%Y%m%d')
#file = 'F:/QutData/TickersList_'+dateToday+'.csv'
#tickersRawData.to_csv(file)
#print ('Tickers saved')

for i, ticker in enumerate(tickers):
	try:
		print ('intraday', i, '/', len(tickers))
		stockPriceIntraday(ticker)
		time.sleep(0.2)
	except:
		pass
#	if i>1:
#	   break 
print ('intraday for all stocks got.')


