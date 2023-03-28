from time import sleep
from pytdx.hq import TdxHq_API
import pandas as pd
import tushare as ts
from sqlalchemy import create_engine
from pytdx.config.hosts import hq_hosts


api = TdxHq_API()
api = TdxHq_API(heartbeat=True)
#api = TdxHq_API(auto_retry=True)
home = '10.145.254.55:5432'
job = '10.145.254.56'
ip = job
Cate = 9


#category(K线种类): 5分钟K线(0), 1分钟K线(8), 日K线(9)
"""

"""


eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
StockLists =  pd.read_sql('StocksList', eng).code.tolist()

with api.connect('119.147.212.81', 7709):
    for i, StockCode in enumerate(StockLists):
        print('Index', i, '/', len(StockLists))
        StockData = pd.DataFrame(columns=['open', 'close', 'high', 'low', 'vol', 'amount', 'year', 'month', 'day', 'hour', 'minute', 'datetime'])

        if StockCode[:1] == '6':
            nn = 1
        else:
            nn = 0
        
        try:
            StockData = api.to_df(api.get_security_bars(Cate, nn, StockCode, 1, 24))
            DayUp = StockData.head(1)['datetime'].tolist()[0]
            Day = pd.read_sql(StockCode, eng)['datetime'].tail(1).tolist()[0]       
            if DayUp > Day:
                StockData.set_index('datetime', inplace=True)
                StockData.to_sql(StockCode, eng, if_exists='append')
                print(StockCode,'saved to sql !')
            else:
                print(StockCode,'pass !')
                pass

        except:
            pass
            # if DayUp is not None:
            #     StockData.set_index('datetime', inplace=True)
            #     StockData.to_sql(StockCode, eng, if_exists='append')
            #     print(StockCode,'New Stock saved to sql !') 
            # else:
            #     pass                  

print(' == 通达信每日更新 股票 行情完成 ! ==')