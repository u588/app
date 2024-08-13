from pytdx.hq import TdxHq_API
import pandas as pd
from sqlalchemy import create_engine


api = TdxHq_API()
api = TdxHq_API(heartbeat=True)

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxStocks')
StockLists =  pd.read_sql('StocksList', eng).code.tolist()

with api.connect('119.147.212.81', 7709):
    for i, StockCode in enumerate(StockLists):
        print('Index', i, '/', len(StockLists))
        StockData = pd.DataFrame()
        if StockCode[:1] == '6':
            nn = 1
        else:
            nn = 0    
        try:
            start = 5500
            while start >= 0:
                df = api.to_df(api.get_security_bars(9, nn, StockCode, start, 500))
                start = start - 500
                StockData = pd.concat([StockData,df])

            StockData.set_index('datetime', inplace=True)
            StockData.to_sql(StockCode, eng, if_exists='replace')
        except:
            pass
        print(StockCode,'saved to sql !')
