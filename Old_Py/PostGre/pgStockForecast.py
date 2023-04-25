from sqlalchemy import create_engine
import tushare as ts
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/Forecast')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

def GetStockForecast(ticker):
    StockForecast = pro.income(ts_code=ticker)
    StockForecast = StockForecast.set_index('end_date')
    StockForecast.sort_index(inplace=True)
    StockForecast.reset_index(inplace=True)
    if pd.io.sql.has_table(ticker, eng):
        history = pd.read_sql(ticker, eng)
        stamp = history.tail(1)['end_date'].tolist()[0]
        StockForecast = StockForecast[(StockForecast['end_date']>stamp)]
    StockForecast.set_index(['end_date'], inplace=True)
    pd.io.sql.to_sql(StockForecast, ticker, eng, if_exists='append')
    print ('intraday for ['+ticker+'] got.')

tickersRawData = pro.stock_basic()
tickers = tickersRawData.loc[:, ['ts_code']].ts_code.tolist()


for i, ticker in enumerate(tickers):
    try:
    	print ('intraday', i, '/', len(tickers))
    	GetStockForecast(ticker)
    	time.sleep(0.2)
    except:
    	pass
    # if i>0:
    #    break 
print ('intraday for all stocks got.')