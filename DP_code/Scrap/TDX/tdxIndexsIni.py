from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API
import pandas as pd
from sqlalchemy import create_engine


eapi =  TdxExHq_API()
api = TdxHq_API()
# api = TdxHq_API(heartbeat=True)
#api = TdxHq_API(auto_retry=True)


"""
category(K线种类): 5分钟K线(0), 1分钟K线(8), 日K线(9)
============== 7709 ============
HostName01=深圳双线主站1
IPAddress01=110.41.147.114
HostName04=深圳双线主站4
IPAddress04=47.113.94.204

HostName07=上海双线主站1
IPAddress07=124.70.176.52
HostName08=上海双线主站2
IPAddress08=47.100.236.28

HostName13=北京双线主站1
IPAddress13=121.36.54.217
HostName15=北京双线主站3
IPAddress15=123.249.15.60


============= 7727 ================
182.175.240.157


HostName01=扩展市场深圳双线1
IPAddress01=112.74.214.43
HostName02=扩展市场深圳双线2
IPAddress02=120.25.218.6

HostName08=扩展市场上海双线1
IPAddress08=106.14.95.149
HostName09=扩展市场上海双线2
IPAddress09=47.102.108.214

HostName12=扩展市场广州双线1
IPAddress12=116.205.143.214
HostName13=扩展市场广州双线2
IPAddress13=124.71.223.19

"""


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxIndex')


tdxIndexs = pd.read_sql('optIndexs', eng)
sh = tdxIndexs[tdxIndexs['MarketCode'] == 1 ]
sz = tdxIndexs[tdxIndexs['MarketCode'] == 0 ]
zz = tdxIndexs[tdxIndexs['MarketCode'] == 62 ]
ll = []

with api.connect('110.41.147.114', 7709):
    IndexLists=sh.IndexCode.to_list()   
    for i, IndexCode in enumerate(IndexLists):
        try:                
            print('Index', i, '/', len(IndexLists))
            IndexData = pd.DataFrame()
            # IndexData = pd.DataFrame(columns=['open', 'close', 'high', 'low', 'vol', 'amount', 'year', 'month', 'day', 'hour', 'minute', 'datetime', 'up_count', 'down_count'])
            start = 5500
            while start >= 0:
                df = api.to_df(api.get_index_bars(9, 1, IndexCode, start, 500))
                start = start - 500
                if df.empty:
                    pass
                else:
                    IndexData = pd.concat([IndexData,df])
            if IndexData.empty:
                ll.append(IndexCode)
            else:
                IndexData.set_index('datetime', inplace=True)
                IndexData.to_sql(IndexCode, eng, if_exists='replace')
                print(IndexCode,'saved to sql !')
        except:
            print(IndexCode, 'no saved to sql !' )
            pass
        
    IndexLists=sz.IndexCode.to_list()   
    for i, IndexCode in enumerate(IndexLists):
        try:                
            print('Index', i, '/', len(IndexLists))
            IndexData = pd.DataFrame()
            # IndexData = pd.DataFrame(columns=['open', 'close', 'high', 'low', 'vol', 'amount', 'year', 'month', 'day', 'hour', 'minute', 'datetime', 'up_count', 'down_count'])
            start = 5500
            while start >= 0:
                df = api.to_df(api.get_index_bars(9, 0, IndexCode, start, 500))
                start = start - 500
                if df.empty:
                    pass
                else:
                    IndexData = pd.concat([IndexData,df])
            if IndexData.empty:
               ll.append(IndexCode)
            else:
                IndexData.set_index('datetime', inplace=True)
                IndexData.to_sql(IndexCode, eng, if_exists='replace')
                print(IndexCode,'saved to sql !')
        except:
            print(IndexCode, 'no saved to sql !' )
            pass

# with eapi.connect('182.175.240.157', 7727):
with eapi.connect('47.112.95.207', 7720):
    IndexLists=zz.IndexCode.to_list()   
    for i, IndexCode in enumerate(IndexLists):
        try:                
            print('Index', i, '/', len(IndexLists))
            # IndexData = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'position', 'trade','price', 'year', 'month', 'day', 'hour', 'minute', 'datetime', 'amount'])
            IndexData = pd.DataFrame()
            start = 5500
            while start >= 0:
                df = eapi.to_df(eapi.get_instrument_bars(9, 62, IndexCode, start, 500))
                start = start - 500
                if df.empty:
                    pass
                else:
                    IndexData = pd.concat([IndexData,df])
            if IndexData.empty:
                ll.append(IndexCode)
            else:
                IndexData.set_index('datetime', inplace=True)
                IndexData.to_sql(IndexCode, eng, if_exists='replace')
                print(IndexCode,'saved to sql !')
        except:
            print(IndexCode, 'no saved to sql !' )
            pass
pd.DataFrame(ll,columns=['IndexCode']).to_sql('EmpIndex', eng, if_exists='replace')     
print(' == 通达信 指数 行情初始化完成 ! ==')
eng.dispose()