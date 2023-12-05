import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
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
pcb5 = df[['datetime', 'PCB5','PCB5time', 'PCB5time13']]
pcb13 = df[['datetime', 'PCB13','PCB13time', 'PCB13time34']]
pcb21 = df[['datetime', 'PCB21','PCB21time', 'PCB21time55']]

def GetPCB(pcb,m,g):
    dd = pd.DataFrame()
    n = 0
    while n < len(pcb):
        try:
            if pcb[pcb.columns[1]][n:n+m].max() > g :
                # print(n)
                i = pcb[pcb.columns[1]][n:n+m][pcb[pcb.columns[1]]==pcb[pcb.columns[1]][n:n+m].max()].index.values[0]
                n = pcb[pcb.columns[1]][i:i+m][pcb[pcb.columns[1]]==pcb[pcb.columns[1]][i:i+m].max()].index.values[0]
                dd = pd.concat([dd,pcb.loc[n].to_frame().T])
                n = n + m 
            else:
                n = n + 1
        except:
            n = n + 1
            pass
    return dd


# df.to_sql('Index0', engAn, if_exists='replace')
pcb = [[pcb3,3,4],[pcb5,5,6],[pcb13,13,10],[pcb21,21,15]]
for n  in pcb:
    a = GetPCB(n[0],n[1],n[2]).reset_index(drop=True)
    a['Num'] = pd.to_datetime(a.datetime)-pd.to_datetime(a.shift(1).datetime)
    a.to_excel('g:/1/StPCB'+str(n[1])+'.xlsx')
# df.to_excel('g:/1/stock0.xlsx')
