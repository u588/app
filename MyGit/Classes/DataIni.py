from sqlalchemy import create_engine
import pandas as pd

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs')
engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
"""
    数据同步到本地
"""
IndexOne = pd.read_sql('IndexOne', eng)
IndexOne.set_index('datetime', inplace=True)
IndexOne.to_csv('f:/IndexOne.csv')
print('IndexOne saved.')

IndexList = pd.read_sql('IndexList', eng)
IndexList.set_index('index_code', inplace=True)
IndexList.to_csv('f:/IndexList.csv', encoding='utf-8')
print('IndexList saved.')

IndexConst = pd.read_sql('IndexConst', eng)
IndexConst.set_index('index_code', inplace=True)
IndexConst.to_csv('f:/IndexConst.csv', encoding='utf-8')
print('IndexConst saved.')

StockLists = pd.read_sql('StockLists', engS)[['ts_code', 'code', 'name', 'list_date']]
StockLists.set_index('ts_code', inplace=True)
StockLists.to_csv('f:/StockLists.csv', encoding='utf-8')
print('f:/StockLists.csv saved.')