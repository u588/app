import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

df = pd.read_sql('000001', eng)
eng.dispose()

p0 = [3,5,13,21]
p1 = [8,13,34,55]
p0 = [[3,8],[5,13],[13,34],[21,55]]

def GetPCB(df,n,p):
    a = ((df.loc[n].close - df.loc[(n-p)].close)/df.loc[(n-p)].close)*100
    return a.round(2)

for n in df.index[::-1]:
    print(n)
    try:
        for p in p0:
            try:
                df.loc[n, 'PCB'+str(p[0])] = GetPCB(df,n,p[0])
                df.loc[n,'PCB'+str(p[0])+'time'] = df.loc[(n-p[0])].datetime
                df.loc[n,'PCB'+str(p[0])+'time'+str(p[1])] = df.loc[(n-(p[0]+p[1]))].datetime
            except:
                pass
    except:
        pass

df.to_sql('Index0', engAn, if_exists='replace')
df.to_excel('g:/1/Index1.xlsx')
