from sqlalchemy import create_engine
import datetime
import pandas as pd
import time
import stockHolders
import random


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/StockHolders')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')

StockLists = pd.read_sql('StocksList', engs).code.tolist()
random.shuffle(StockLists)

for stockID in StockLists:
    try:
        stockHolders.getStockHolders(stockID).to_sql(stockID, eng, if_exists='replace')
        # print(stockID, 'Saved to sql !')
        time.sleep(random.randint(1,3))
    except:
        print('Not Save! '+stockID)
        pass
print('All Saved !! ')