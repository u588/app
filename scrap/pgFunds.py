from sqlalchemy import create_engine
import pandas as pd
import datetime
import time
import stockFund
import random


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')
StockLists = pd.read_sql('StocksList', engs).code.tolist()

for stockID in StockLists:
    try:
        # if stockID >'002669':
        stockFund.getFunds(stockID).to_sql(stockID, eng, if_exists='replace')
        # print(stockID, 'Saved to sql !')
        time.sleep(random.randint(1,3))
        # else:
            # pass
    except:
        print('Not Save! '+stockID)
        pass
print('all saved !')

