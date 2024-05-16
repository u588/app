from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')

tdx= pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/Findex.xlsx', dtype={'IndexCode':object})
tdx.set_index('IndexName').to_sql('tdxIndexs',eng, if_exists = 'replace')