from sqlalchemy import create_engine
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndexs')

Stocks = ['600312','000400']

for Stock in Stocks:
    try:
        IndexConst = pd.read_sql('IndexConst', eng)
        StockInIndex = IndexConst[IndexConst.code==Stock][['index_code', 'code','name']]
        StockInIndex.rename(columns={'name':'stock_name','code':'stock_code'}, inplace=True)
        csIndex = pd.read_sql('IndexList', eng)
        csIndex =csIndex[['index_code', 'index_name']]
        # csIndex.rename(columns={'name':'index_name'}, inplace=True)
        dd = pd.merge(StockInIndex, csIndex, on='index_code')
        dd.to_excel('/home/ts/app/data/' + Stock + '.csv')
        print('ok')
    except:
        pass


