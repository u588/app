from sqlalchemy import create_engine
import pandas as pd
import datetime
import time
import stockDetail
import random


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/StockBas')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')
ll = pd.read_sql('StocksList', engs).code.tolist()
sl = pd.read_sql('StocksDetail', eng).code.tolist()
StockLists = list(set(ll)-set(sl))


for stockID in StockLists:
    try:
        stockDetail.getDetail(stockID).to_sql('StocksDetail', eng, if_exists='append')
        stockDetail.getManag(stockID).to_sql('StocksManags', eng, if_exists='append')
        a,b=stockDetail.getAff(stockID)
        a.to_sql('StocksAffs', eng, if_exists='append')
        b['code'] = stockID
        bb = b.reset_index().set_index('code')
        bb.to_sql('AffManags', eng, if_exists='append')
        # print(stockID, 'Saved to sql !')
        time.sleep(random.randint(1,3))

    except:
        print('Not Save! '+stockID)
        pass
print('All Saved !')
