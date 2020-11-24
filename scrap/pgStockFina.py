from sqlalchemy import create_engine
import datetime
import pandas as pd
import time
import stockFina
import random


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/StockFina')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')

StockLists = pd.read_sql('StocksList', engs).code.tolist()

for stockID in StockLists:
    try:
        a = stockFina.getFina(stockID)
        b = pd.read_excel('/home/ts/app/ccl.xls')
        m = pd.merge(b,a,how='outer')
        m.iloc[1] = m.columns.values
        m.columns = m.iloc[0]
        m.drop(0, inplace=True)
        m.to_sql(stockID, eng, if_exists='replace')
        # print(stockID, 'Saved to sql !')
        time.sleep(random.randint(1,3))
    except:
        print('Not Save! '+stockID)
        pass

print('All Saved !! ')
