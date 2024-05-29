from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')

tdx= pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsConsBLK.xlsx', dtype={'IndexCode':object ,'StockCode':object})
cs = pd.read_sql('csIndexCons', eng)

df = pd.concat([tdx,cs]).reset_index(drop=True)
df.set_index('IndexCode').to_sql('IndexCons',eng, if_exists = 'replace')

print('Saved ! ')