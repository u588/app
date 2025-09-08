from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')

blkDF = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxIndexsConsBLK.xlsx', dtype={'IndexCode':object,'StockCode':object})
akDF = pd.read_sql('akIndexCons', eng)

df = pd.concat([blkDF,akDF]).drop_duplicates(subset=['IndexCode','StockCode'])
df.set_index('IndexCode').to_sql('IndexCons',eng, if_exists = 'replace')
print('update OK !')