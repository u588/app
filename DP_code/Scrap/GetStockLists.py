from sqlalchemy import create_engine
import tushare as ts
# import pandas  as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxStocks')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')
pro = ts.pro_api()

StockLists = pro.stock_basic()
StockLists = StockLists[~StockLists['name'].str.contains('退')]
StockLists = StockLists[~(StockLists.market =='北交所')]
if StockLists.shape[0]>3000:
    StockLists.rename(columns={'symbol':'code'}, inplace=True)
    StockLists.set_index('ts_code', inplace=True)
    StockLists.to_sql('StocksList', eng, if_exists='replace')
    print(' == 本周 ' + str(StockLists.shape[0]) + ' 股票编码更新 !')
else:
    pass
    print(' == 有错误！==')
