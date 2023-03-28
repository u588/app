from pytdx.hq import TdxHq_API
import pandas as pd
import tushare as ts
from sqlalchemy import create_engine
from pytdx.config.hosts import hq_hosts


api = TdxHq_API()
api = TdxHq_API(heartbeat=True)
#api = TdxHq_API(auto_retry=True)
home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job
Cate = 9


#category(K线种类): 5分钟K线(0), 1分钟K线(8), 日K线(9)
"""
    [1] :招商证券深圳行情 (119.147.212.81:7709)
    [2] :华泰证券(南京电信) (221.231.141.60:7709)
    [3] :华泰证券(上海电信) (101.227.73.20:7709)
    [4] :华泰证券(上海电信二) (101.227.77.254:7709)
    [5] :华泰证券(深圳电信) (14.215.128.18:7709)
    [6] :华泰证券(武汉电信) (59.173.18.140:7709)
    [7] :华泰证券(天津联通) (60.28.23.80:7709)
    [8] :华泰证券(沈阳联通) (218.60.29.136:7709)
    [9] :华泰证券(南京联通) (122.192.35.44:7709)
    [10] :华泰证券(南京联通) (122.192.35.44:7709)

"""


eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
StockLists =  pd.read_sql('StocksList', eng).code.tolist()

with api.connect('119.147.212.81', 7709):
    try:
        for i, StockCode in enumerate(StockLists):
            print('Index', i, '/', len(StockLists))
            StockData = pd.DataFrame(columns=['open', 'close', 'high', 'low', 'vol', 'amount', 'year', 'month', 'day', 'hour', 'minute', 'datetime'])
            sql = 'select * from "'+StockCode+'" order by datetime desc limit 1 ;'    
            if StockCode[:2] == '60':
                StockData = api.to_df(api.get_security_bars(Cate, 1, StockCode, 0, 1))
                DayUp = StockData.head(1)['datetime'].tolist()[0]
                try:
                    Day = pd.read_sql(sql, eng)['datetime'].tolist()[0]        
                    if DayUp > Day:
                        StockData.set_index('datetime', inplace=True)
                        StockData.to_sql(StockCode, eng, if_exists='append')
                        print(StockCode,'saved to sql !')
                    else:
                        pass

                except:
                    StockData.set_index('datetime', inplace=True)
                    StockData.to_sql(StockCode, eng, if_exists='append')
                    print(StockCode,'saved to sql !')                    

            else:
                StockData = api.to_df(api.get_security_bars(Cate, 0, StockCode, 0, 1))
                DayUp = StockData.head(1)['datetime'].tolist()[0]
                try:
                    Day = pd.read_sql(sql, eng)['datetime'].tolist()[0]
                    if DayUp > Day:
                        StockData.set_index('datetime', inplace=True)
                        StockData.to_sql(StockCode, eng, if_exists='append')
                        print(StockCode,'saved to sql !')
                    else:
                        pass
                except:
                    StockData.set_index('datetime', inplace=True)
                    StockData.to_sql(StockCode, eng, if_exists='append')
                    print(StockCode,'saved to sql !')
                
    except:
        pass