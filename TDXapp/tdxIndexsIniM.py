from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API
import pandas as pd
from sqlalchemy import create_engine


eapi =  TdxExHq_API()
api = TdxHq_API()

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxIndex')

# optO = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/optIndexsO.xlsx',dtype={'IndexCode':object} )
opt = pd.read_sql('optIndexs', eng)
# tdxIndexs = pd.read_sql('optIndexs', eng)
# tdxIndexs = opt[~(opt['IndexCode'].isin(optO['IndexCode']))]
tdxIndexs = opt[opt['IndexCode'].str.startswith('881')]

sh = tdxIndexs[tdxIndexs['MarketCode'] == 1 ]
sz = tdxIndexs[tdxIndexs['MarketCode'] == 0 ]
zz = tdxIndexs[tdxIndexs['MarketCode'] == 62 ]
gz = tdxIndexs[tdxIndexs['MarketCode'] == 102 ]

with api.connect('180.153.18.170', 7709):
    IndexLists=sh['IndexCode']   
    for i, IndexCode in enumerate(IndexLists):
        try:                
            print('Index', i, '/', len(IndexLists))
            IndexData = pd.DataFrame(columns=['open', 'close', 'high', 'low', 'vol', 'amount', 'year', 'month', 'day', 'hour', 'minute', 'datetime', 'up_count', 'down_count'])
            start = 5500
            while start >= 0:
                df = api.to_df(api.get_index_bars(9, 1, IndexCode, start, 500))
                start = start - 500
                if df.empty:
                    pass
                else:
                    IndexData = pd.concat([IndexData.astype(df.dtypes),df])
            IndexData.dropna(thresh=6, inplace=True)
            IndexData.set_index('datetime', inplace=True)
            IndexData.to_sql(IndexCode, eng, if_exists='replace')
            print(IndexCode,'saved to sql !')

        except:
            print(IndexCode, 'no saved to sql !' )
            pass
        
    IndexLists=sz['IndexCode']    
    for i, IndexCode in enumerate(IndexLists):
        try:                
            print('Index', i, '/', len(IndexLists))
            IndexData = pd.DataFrame(columns=['open', 'close', 'high', 'low', 'vol', 'amount', 'year', 'month', 'day', 'hour', 'minute', 'datetime', 'up_count', 'down_count'])
            start = 5500
            while start >= 0:
                df = api.to_df(api.get_index_bars(9, 0, IndexCode, start, 500))
                start = start - 500
                if df.empty:
                    pass
                else:
                    IndexData = pd.concat([IndexData.astype(df.dtypes),df])
            IndexData.dropna(thresh=6, inplace=True)
            IndexData.set_index('datetime', inplace=True)
            IndexData.to_sql(IndexCode, eng, if_exists='replace')
            print(IndexCode,'saved to sql !')

        except:
            print(IndexCode, 'no saved to sql !' )
            pass
        

with eapi.connect('47.112.95.207', 7720):
    IndexLists=zz['IndexCode']    
    for i, IndexCode in enumerate(IndexLists):
        try:                
            print('Index', i, '/', len(IndexLists))
            IndexData = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'position', 'trade','price', 'year', 'month', 'day', 'hour', 'minute', 'datetime', 'amount'])
            start = 5500
            while start >= 0:
                df = eapi.to_df(eapi.get_instrument_bars(9, 62, IndexCode, start, 500))
                start = start - 500
                if df.empty:
                    pass
                else:
                    IndexData = pd.concat([IndexData.astype(df.dtypes),df])
            IndexData.dropna(thresh=6, inplace=True)
            IndexData.set_index('datetime', inplace=True)
            IndexData.to_sql(IndexCode, eng, if_exists='replace')
            print(IndexCode,'saved to sql !')

        except:
            print(IndexCode, 'no saved to sql !' )
            pass
    IndexLists=gz['IndexCode']    
    for i, IndexCode in enumerate(IndexLists):
        try:                
            print('Index', i, '/', len(IndexLists))
            IndexData = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'position', 'trade','price', 'year', 'month', 'day', 'hour', 'minute', 'datetime', 'amount'])
            start = 5500
            while start >= 0:
                df = eapi.to_df(eapi.get_instrument_bars(9, 102, IndexCode, start, 500))
                start = start - 500
                if df.empty:
                    pass
                else:
                    IndexData = pd.concat([IndexData.astype(df.dtypes),df])
            IndexData.dropna(thresh=6, inplace=True)
            IndexData.set_index('datetime', inplace=True)
            IndexData.to_sql(IndexCode, eng, if_exists='replace')
            print(IndexCode,'saved to sql !')

        except:
            print(IndexCode, 'no saved to sql !' )
            pass
eng.dispose()        
print(' == 通达信 指数 行情初始化完成 ! ==')