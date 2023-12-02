import pandas as pd
from sklearn import preprocessing
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')
engS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

Stocks = pd.read_sql('cicsClass', eng)
eng.dispose()

startDay = '2005-11-01 15:00'
endDay = '2005-12-07 15:00'

def getValues(code,start,end):
    ff = pd.read_sql(code, engS)
    engS.dispose()
    a = (ff[ff.datetime==end].close.values\
         -ff[ff.datetime==start].close.values)\
            /ff[ff.datetime==start].close.values*100
    return a.round(2)[0]

for i,code in enumerate(Stocks.code):
    try:
        Stocks.loc[i,'PCB'] = getValues(code,startDay,endDay)
    except:
        pass
Stocks.set_index('code').to_sql('PCB1',engAn,if_exists='replace')
engAn.dispose()
