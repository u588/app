from time import sleep
from pytdx.hq import TdxHq_API
import pandas as pd
import tushare as ts
from sqlalchemy import create_engine
from pytdx.config.hosts import hq_hosts


api = TdxHq_API()
api = TdxHq_API(heartbeat=True)
#api = TdxHq_API(auto_retry=True)

job = '10.145.254.56'
ip = job
Cate = 9


#category(K线种类): 5分钟K线(0), 1分钟K线(8), 日K线(9)
"""
    [1] :招商证券深圳行情 (119.147.212.81:7709)
    [2] :上证云北京联通一 (123.125.108.14:7709)
    [3] :上证云成都电信一 (218.6.170.47:7709)
    [4] :华泰证券(上海电信二) (101.227.77.254:7709)
    [5] :华泰证券(深圳电信) (14.215.128.18:7709)
    [6] :华泰证券(武汉电信) (59.173.18.140:7709)
    [7] :华泰证券(天津联通) (60.28.23.80:7709)
    [8] :华泰证券(沈阳联通) (218.60.29.136:7709)
    [9] :华泰证券(南京联通) (122.192.35.44:7709)
    [10] :华泰证券(南京联通) (122.192.35.44:7709)
上海电信主站Z1=180.153.18.170:7709

上海电信主站Z2=180.153.18.171:7709

上海电信主站Z80=180.153.18.172:80

北京联通主站Z1=202.108.253.130:7709

北京联通主站Z2=202.108.253.131:7709

北京联通主站Z80=202.108.253.139:80

杭州电信主站J1=60.191.117.167:7709

杭州电信主站J2=115.238.56.198:7709

杭州电信主站J3=218.75.126.9:7709

杭州电信主站J4=115.238.90.165:7709

杭州联通主站J1=124.160.88.183:7709

杭州联通主站J2=60.12.136.250:7709

杭州华数主站J1=218.108.98.244:7709

杭州华数主站J2=218.108.47.69:7709

义乌移动主站J1=223.94.89.115:7709

青岛联通主站W1=218.57.11.101:7709

青岛电信主站W1=58.58.33.123:7709

深圳电信主站Z1=14.17.75.71:7709

云行情上海电信Z1=114.80.63.12:7709

云行情上海电信Z2=114.80.63.35:7709

上海电信主站Z3=180.153.39.51:7709

"""


eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
StockLists =  pd.read_sql('StocksList', eng).code.tolist()

with api.connect('180.153.18.170', 7709):
    for i, StockCode in enumerate(StockLists):
        # print('Index', i, '/', len(StockLists))
        StockData = pd.DataFrame(columns=['open', 'close', 'high', 'low', 'vol', 'amount', 'year', 'month', 'day', 'hour', 'minute', 'datetime'])

        if StockCode[:1] == '6':
            nn = 1
        else:
            nn = 0

        StockData = api.to_df(api.get_security_bars(Cate, nn, StockCode, 0,3))
        if StockData.empty:
            pass
        else:
            try:            
                DayUp = StockData.head(1)['datetime'].tolist()[0]
                Day = pd.read_sql(StockCode, eng)['datetime'].tail(1).tolist()[0]       
                if DayUp > Day:
                    StockData.set_index('datetime', inplace=True)
                    StockData.to_sql(StockCode, eng, if_exists='append')
                    #print(StockCode,'saved to sql !')
                else:
                    print(StockCode,'pass !')
                    pass

            except:
                StockData.set_index('datetime', inplace=True)
                StockData.to_sql(StockCode, eng, if_exists='append')
                print(StockCode,'New Stock saved to sql !') 
    

print(' == 通达信每日更新 股票 行情完成 ! ==')