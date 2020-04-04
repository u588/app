from sqlalchemy import create_engine
import pandas as pd
"""
    所选股票属于那些指数
"""

home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/csIndex')

Stocks = ['601989','600409','601600', '000839', '000792', '600256','600312','000400']

for Stock in Stocks:
    try:
        IndexConst = pd.read_sql('IndexConst', eng)
        StockInIndex = IndexConst[IndexConst.code==Stock][['index_code', 'code','name']]
        StockInIndex.rename(columns={'name':'stock_name','code':'stock_code'}, inplace=True)
        csIndex = pd.read_sql('IndexList', eng)
        csIndex =csIndex[['index_code', 'name', 'const']]
        csIndex.rename(columns={'name':'index_name'}, inplace=True)
        dd = pd.merge(StockInIndex, csIndex, on='index_code')
        dd.to_excel('f:/股票指数分布/' + Stock + '.xls')
    except:
        pass
