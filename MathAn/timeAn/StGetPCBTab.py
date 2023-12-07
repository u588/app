import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

code = '000001'
rawD = pd.read_sql(code, eng)
dff = rawD[rawD.datetime >= '2000-01-01'].reset_index(drop=True)
dff['mea'] = (dff.amount/(dff.vol*100)).round(2)
df = dff[['datetime','open','close','high','low','mea','vol','amount']]
eng.dispose()

p0 = [[5,13],[13,34]]

#第二个参数n涨幅周期，第三个参数p回测周期。
def GetPCBraw(df,n,p):
    a = ((df.loc[n].close - df.loc[(n-p)].close)/df.loc[(n-p)].close)*100
    return a.round(2)

for n in df.index[::-1]:
    print(n)
    try:
        for p in p0:
            try:
                df.loc[n, 'PCB'+str(p[0])] = GetPCBraw(df,n,p[0])
                df.loc[n,'PCB'+str(p[0])+'time'] = df.loc[(n-p[0])].datetime
                df.loc[n,'PCB'+str(p[0])+'time'+str(p[1])] = df.loc[(n-(p[0]+p[1]))].datetime
            except:
                pass
    except:
        pass

pcb5 = df[['datetime', 'PCB5','PCB5time', 'PCB5time13']]
pcb13 = df[['datetime', 'PCB13','PCB13time', 'PCB13time34']]

#第二个参数m涨幅周期，第三个参数选择涨幅大于g的记录。
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

pcb = [[pcb5,5,8],[pcb13,13,16]]
for n  in pcb:
    a = GetPCB(n[0],n[1],n[2]).reset_index(drop=True)
    a['Num'] = pd.to_datetime(a.datetime)-pd.to_datetime(a.shift(1).datetime)
    a.set_index('datetime').to_excel('g:/1/2/St'+code + 'PCB'+str(n[1])+'.xlsx')
df.set_index('datetime').to_excel('g:/1/2/St'+code + '.xlsx')
