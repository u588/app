from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/csIndex')

IndexOne = pd.read_csv('f:/indexone.csv', index_col=0)

IndexCodess = pd.read_sql('IndexList', eng)
IndexCodes = IndexCodess.code.tolist()

for i, IndexCode in enumerate(IndexCodes):
    print ('IndexCode', i, '/', len(IndexCodes))
    try:
        IndexCodess[IndexCode] = 0
        for i, IndexCo in enumerate(IndexCodes):
            print ('ICode', i, '/', len(IndexCodes))
            
            try:
  #              print(IndexOne[IndexCode[2:]])
                IndexCodess.loc[i,[IndexCode]] = IndexOne[IndexCode[2:]].corr(IndexOne[IndexCo[2:]])
                print(IndexCodess.loc[i,[IndexCode]])
            except:
                pass
            if i>2:
                break
    except:
        pass
    if i>2:
       break
#print(IndexCodess.head())
#IndexCodess.to_csv('f:/corr2.csv')