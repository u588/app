from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
import datetime



eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/db')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()
dateToday = datetime.datetime.today().strftime('%Y%m%d')

def AdjStock(ticker):
    intraday = pro.adj_factor(ts_code=ticker, trade_date = dateToday)
    intraday = intraday.set_index('trade_date')
    intraday.sort_index(inplace=True)
    pd.io.sql.to_sql(intraday, 'adj' + ticker, eng, if_exists='append')

#    print ('复权因子 for ['+ticker+'] got.')

tickersRawData = pro.stock_basic()
tickers = tickersRawData.ts_code.tolist()


for i, ticker in enumerate(tickers):
    try:
    	print ('stock', i, '/', len(tickers))
    	AdjStock(ticker)
    	time.sleep(0.2)
    except:
    	pass
#    if i>1:
#      break 
#print ('复权因子 for all stocks got.')
