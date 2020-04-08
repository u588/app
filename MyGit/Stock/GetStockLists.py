from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd


home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')
pro = ts.pro_api()

StockLists = pro.stock_basic()
StockLists = StockLists[~StockLists['name'].str.contains('退')]
StockLists.rename(columns={'symbol':'code'}, inplace=True)
StockLists.set_index('ts_code', inplace=True)
StockLists.to_sql('StockLists', eng, if_exists='replace')
