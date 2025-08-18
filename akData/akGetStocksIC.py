# 数据限制 20000
import akshare as ak
from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')

StockList = pd.read_sql('akStocksList', eng)
StocksCode = StockList['StockCode'].tolist()

idf = ak.stock_industry_change_cninfo(symbol=StocksCode[0], start_date="11000101", end_date="22000101")
for code in StocksCode[1:]:
    df_tmp = ak.stock_industry_change_cninfo(symbol=code, start_date="11000101", end_date="22000101")
    idf = pd.concat([idf,df_tmp])
    print('code '+code+' :concat !')