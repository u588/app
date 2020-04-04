from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
import datetime


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/db')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

def stockPriceIntraday(ticker,i):
	intraday = tickersRawData.loc[i:i]
	intraday.set_index(['timestamp'], inplace=True)
	pd.io.sql.to_sql(intraday, ticker, eng, if_exists='append')
#	print ('intraday for ['+ticker+'] got.')

dateToday = datetime.datetime.today().strftime('%Y%m%d')
tickersRawData = pro.daily(trade_date=dateToday)
tickersRawData.rename(columns={'trade_date':'timestamp'}, inplace=True)
tickers = tickersRawData.ts_code.tolist()
# file = 'F:/QutData/TickersDaily_'+dateToday+'.csv'
# tickersRawData.to_csv(file)
# print ('Tickers saved')

for i, ticker in enumerate(tickers):
	try:
#		print(ticker)
#		print ('intraday', i, '/', len(tickers))
		stockPriceIntraday(ticker,i)
		time.sleep(0.2)
	except:
		pass
#	if i>0:
#	   break 
print ('intraday for all stocks got.')

