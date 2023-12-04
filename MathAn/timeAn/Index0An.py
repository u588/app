import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

df = pd.read_sql('000001', eng)
eng.dispose()

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

pcb3 = df[['datetime', 'PCB3','PCB3time', 'PCB3time8']]
pcb5 = df[['datetime', 'PCB5','PCB5time', 'PCBtime13']]
pcb13 = df[['datetime', 'PCB13','PCB13time', 'PCB13time34']]
pcb21 = df[['datetime', 'PCB21','PCB21time', 'PCB21time55']]

n = 0
while n < len(pcb3):
    try:
        if pcb3.PCB3[n:n+3].max() > 4 :
           i = pcb3.PCB3[n:n+3][pcb3.PCB3==pcb3.PCB3[n:n+3].max()].index.values[0]
           n = pcb3.PCB3[i:i+3][pcb3.PCB3==pcb3.PCB3[i:i+3].max()].index.values[0]

        elif:
            n = n + 1



df.to_sql('Index0', engAn, if_exists='replace')
df.to_excel('g:/1/Index1.xlsx')
