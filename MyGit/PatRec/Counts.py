import pandas as pd


CodeId = '000001'

data = pd.read_csv('f:/StocksData'+CodeId+'.csv', index_col=0, dtype={'code':object})
StocksList = pd.read_csv('f:/WWWstocks/StocksList.csv', dtype={'code':object})
Stock = StocksList.loc[StocksList['code']==CodeId].astype(str)

 # data[(data['sum3']>5)&(data['sum5']<13)]['sum3'].count()