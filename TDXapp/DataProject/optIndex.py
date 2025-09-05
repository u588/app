import pandas as pd
from sqlalchemy import create_engine

# eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')

dropdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/dropIndexs.xlsx', dtype={'IndexCode':object})
empdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/empIndexs.xlsx', dtype={'IndexCode':object})
tdxdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexs.xlsx', dtype={'IndexCode':object})

optDF = pd.concat([tdxdf,dropdf]).drop_duplicates(subset='IndexCode',keep=False).sort_values(by=['IndexCode','MarketCode'])

optDF.loc[optDF['IndexCode'].isin(empdf['IndexCode']), 'From'] = 'EMP'
optDF.dropna(subset='IndexSTL').set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/optIndexs.xlsx')

print('Saved ! ')