import pandas as pd
from sqlalchemy import create_engine


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxIndex')

CsCons = pd.read_sql('csIndexCon',eng)
BLKCons = pd.read_excel('G:/Gitee/App/tdxAppData/1tdxIndexsConsBLK.xlsx', dtype={'IndexCode':object, 'StockCode':object})
GUICons = pd.read_excel('G:/Gitee/App/tdxAppData/1tdxGuiIndexCons.xlsx', dtype={'IndexCode':object, 'StockCode':object})

df = pd.DataFrame
df = pd.concat([CsCons, BLKCons])
df = pd.concat([df,GUICons])

df.drop_duplicates().set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/FinaltdxIndexCons622.xlsx')
df.drop_duplicates().set_index('IndexCode').to_sql('IndexCons', eng, if_exists='replace')