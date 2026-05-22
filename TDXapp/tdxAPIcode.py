import pandas as pd
from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API

eapi =  TdxExHq_API()
api = TdxHq_API()

import pandas as pd
from sqlalchemy import create_engine
engF = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxFS')
engI = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')

eapi.connect('47.112.95.207', 7720)

mID = api.to_df(eapi.get_markets())[["market",	"name"]].rename(columns={'name':'market_name'})

df_inst = pd.DataFrame()
total = eapi.get_instrument_count()
for start in range(0, total, 1000):
    df_tmp = api.to_df(eapi.get_instrument_info(start, 999))
    df_inst = pd.concat([df_inst, df_tmp], ignore_index=True)
    
df_merg = pd.merge(df_inst, mID, left_on='market', right_on='market', how='left').rename(columns={'name':'code_name','market':'market_code'})[['code', 'code_name', 'category','market_code', 'market_name']]

df_merg.to_sql('tdxAPIcode', engI, if_exists='replace', index=False)

print('tdxAPI代码表 更新完成 ')