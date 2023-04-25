from sqlalchemy import create_engine
import tushare as ts
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/Express')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

def GetStockExpress(ticker):
    StockExpress = pro.income(ts_code=ticker)
    StockExpress = StockExpress.set_index('end_date')
    StockExpress.sort_index(inplace=True)
    StockExpress.reset_index(inplace=True)
    if pd.io.sql.has_table(ticker, eng):
        history = pd.read_sql(ticker, eng)
        stamp = history.tail(1)['end_date'].tolist()[0]
        StockExpress = StockExpress[(StockExpress['end_date']>stamp)]
    StockExpress.set_index(['end_date'], inplace=True)
    pd.io.sql.to_sql(StockExpress, ticker, eng, if_exists='append')
    print ('intraday for ['+ticker+'] got.')

tickersRawData = pro.stock_basic()
tickers = tickersRawData.loc[:, ['ts_code']].ts_code.tolist()


for i, ticker in enumerate(tickers):
    try:
    	print ('intraday', i, '/', len(tickers))
    	GetStockExpress(ticker)
    	time.sleep(0.2)
    except:
    	pass
    # if i>0:
    #    break 
print ('intraday for all stocks got.')