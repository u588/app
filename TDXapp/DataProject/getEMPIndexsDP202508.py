from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API
import pandas as pd
from sqlalchemy import create_engine


eapi =  TdxExHq_API()
api = TdxHq_API()

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxIndex')

# tdxIndexs = pd.read_sql('optIndexs', eng)
# tdxIndexs = pd.read_sql('tdxIndexs', eng)
tdxIndexs = pd.read_sql('indexM', eng)
sh = tdxIndexs[tdxIndexs['MarketCode'] == 1 ]
sz = tdxIndexs[tdxIndexs['MarketCode'] == 0 ]
zz = tdxIndexs[tdxIndexs['MarketCode'] == 62 ]
ll = []

with api.connect('180.153.18.170', 7709):
    IndexLists=sh.IndexCode.to_list()   
    for i, IndexCode in enumerate(IndexLists):
        try:                
            # print('Index', i, '/', len(IndexLists))
            df = api.to_df(api.get_index_bars(9, 1, IndexCode, 0, 10))
            if df.empty:
                ll.append(IndexCode)
                print(IndexCode+'EMP !! ')
            else:
                pass
        except:
            print(IndexCode, 'EXCEPT !' )
            pass
        
    IndexLists=sz.IndexCode.to_list()   
    for i, IndexCode in enumerate(IndexLists):
        try:                
            # print('Index', i, '/', len(IndexLists))
            df = api.to_df(api.get_index_bars(9, 0, IndexCode, 0, 10))
            if df.empty:
                ll.append(IndexCode)
                print(IndexCode+'EMP !! ')
            else:
               pass
        except:
            print(IndexCode, 'EXCEPT !' )
            pass


with eapi.connect('47.112.95.207', 7720):
    IndexLists=zz.IndexCode.to_list()   
    for i, IndexCode in enumerate(IndexLists):
        try:                
            # print('Index', i, '/', len(IndexLists))
            df = eapi.to_df(eapi.get_instrument_bars(9, 62, IndexCode, 0, 10))
            if df.empty:
                ll.append(IndexCode)
                print(IndexCode+'EMP !! ')
            else:
                pass
        except:
            print(IndexCode, 'EXCEPT !' )
            pass
pd.DataFrame(ll,columns=['IndexCode']).to_sql('EmpIndex', eng, if_exists='replace')     
print(ll)
eng.dispose()