from pytdx.hq import TdxHq_API
import pandas as pd
from sqlalchemy import create_engine

api = TdxHq_API()
api = TdxHq_API(heartbeat=True)
#api = TdxHq_API(auto_retry=True)
home = '10.145.254.55:5432'
job = '10.145.254.56'
ip = job


eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxXdXr')
engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')



StockLists = pd.read_sql('StocksList', engS).code.tolist()

with api.connect('119.147.212.81', 7709):
    try:
        for i, StockCode in enumerate(StockLists):
            print('Index', i, '/', len(StockLists))
            try:
                if StockCode[:1] == '6':
                    StockXdXr = api.to_df(api.get_xdxr_info(1,StockCode))
                else:
                    StockXdXr = api.to_df(api.get_xdxr_info(0,StockCode))
                
                StockXdXr.to_sql(StockCode, eng, if_exists='replace')
                print(StockCode,'XdXr saved !')
            except:
                pass
    except:
        pass
