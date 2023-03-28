from sqlalchemy import create_engine
import pandas as pd
import shutil
import time

home = '10.145.254.55:5432'
job = '10.145.254.56'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs')
engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
"""
    数据同步到本地
"""
#IndexOne = pd.read_sql('IndexOne', eng)
#IndexOne.set_index('datetime', inplace=True)
#IndexOne.to_csv('e:/IndexOne.csv')
#print('IndexOne saved.')

IndexList = pd.read_sql('IndexList', eng)
IndexList.set_index('index_code', inplace=True)
IndexList.to_csv('e:/IndexList.csv', encoding='utf-8')
print('IndexList saved.')

IndexConst = pd.read_sql('IndexConst', eng)
IndexConst.set_index('index_code', inplace=True)
IndexConst.to_csv('e:/IndexConst.csv', encoding='utf-8')
print('IndexConst saved.')

StockLists = pd.read_sql('StocksList', engS)[['ts_code', 'code', 'name', 'list_date']]
StockLists.set_index('ts_code', inplace=True)
StockLists.to_csv('e:/StockLists.csv', encoding='utf-8')
print('e:/StockLists.csv saved.')

shutil.copyfile('E:/StocksOne.csv','Z:/Data/StocksOne.csv')
print('StocksOne.csv saved ! ')
shutil.copyfile('E:/IndexOne.csv','Z:/Data/IndexOne.csv')
print('IndexOne.csv saved ! ')
shutil.copyfile('E:/StocksOne5.csv','Z:/Data/StocksOne5.csv')
print('StocksOne5.csv saved ! ')

shutil.copyfile('E:/IndexList.csv','Z:/Data/IndexList.csv')
print('IndexList.csv saved ! ')
shutil.copyfile('E:/IndexConst.csv','Z:/Data/IndexConst.csv')
print('IndexConst.csv saved ! ')
shutil.copyfile('E:/StockLists.csv','Z:/Data/StockLists.csv')
print('All saved ! ')

