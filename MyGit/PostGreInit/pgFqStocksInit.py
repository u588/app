from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import time

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

engFq = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/Fq')


def FqStock(stock):
    intraday = ts.get_k_data(stock, start='2000-01-01')
    intraday = intraday.set_index('date')
    pd.io.sql.to_sql(intraday, stock, engFq, if_exists='replace')
    print('FqStock for [' + stock + '] got.')

stocks = ts.get_stock_basics().sort_index().index.tolist()

for i, stock in enumerate(stocks):
    try:
        print('FqStock', i, '/', len(stocks))
        FqStock(stock)
        time.sleep(0.2)
    except:
        pass
#    if i>1:
#      break 
print ('FqStock for all stocks got.')
