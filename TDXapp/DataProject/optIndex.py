import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')

tdxIndex = pd.read_sql('tdxIndexs', eng)
empIndex = pd.read_sql('EmpIndex', eng)

df = pd.concat([tdxIndex,empIndex]).drop_duplicates(subset=['IndexCode'], keep=False).drop('index', axis=1)


df.set_index('IndexCode').to_sql('optIndexs',eng, if_exists = 'replace')

# df.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/optIndexs.xlsx')
df.set_index('IndexCode').to_excel('/home/ts/app/TDXapp/tdxAppData/optIndexs.xlsx')
print('Saved ! ')