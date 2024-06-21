import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')

f= pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/indexM.xlsx', dtype={'IndexCode':object})
d= pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/dropIndexs.xlsx', dtype={'IndexCode':object})
d.From='EMP'
ff = pd.concat([d,f]).drop_duplicates(subset='IndexCode')
ff.set_index('IndexCode').to_sql('tdxIndexs',eng, if_exists = 'replace')

ff.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexs.xlsx')
print('Saved ! ')