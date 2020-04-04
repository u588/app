from sqlalchemy import create_engine
import tushare as ts
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/fina_mainbz')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

def GetFinaMaiBZ(ticker):
    FinaMaiBZ = pro.fina_indicator(ts_code=ticker)
    FinaMaiBZ = FinaMaiBZ.set_index('end_date')
    FinaMaiBZ.sort_index(inplace=True)
    FinaMaiBZ.reset_index(inplace=True)
    if pd.io.sql.has_table(ticker, eng):
        history = pd.read_sql(ticker, eng)
        stamp = history.tail(1)['end_date'].tolist()[0]
        FinaMaiBZ = FinaMaiBZ[(FinaMaiBZ['end_date']>stamp)]
    FinaMaiBZ.set_index(['end_date'], inplace=True)
    pd.io.sql.to_sql(FinaMaiBZ, ticker, eng, if_exists='append')
    print ('intraday for ['+ticker+'] got.')

tickersRawData = pro.stock_basic()
tickers = tickersRawData.loc[:, ['ts_code']].ts_code.tolist()


for i, ticker in enumerate(tickers):
    try:
    	print ('intraday', i, '/', len(tickers))
    	GetFinaMaiBZ(ticker)
    	time.sleep(0.2)
    except:
    	pass
    # if i>0:
    #    break 
print ('intraday for all stocks got.')