import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')


OPTdf = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/optIndexs.xlsx',dtype={'IndexCode':object})
EMPdf = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/akEMPB.xlsx', dtype={'IndexCode':object})

finaDF = OPTdf[~OPTdf['IndexCode'].isin(EMPdf['IndexCode'])]


finaDF.set_index('IndexCode').to_sql('optIndexs',eng, if_exists = 'replace')
finaDF.set_index('IndexCode').to_excel('/home/ts/app/TDXapp/tdxAppData/FinaIndexs.xlsx')

eng.dispose()
print('Saved ! ')
