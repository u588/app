import pandas as pd
from sqlalchemy import create_engine
import numpy as np

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

def rvNorm(data):
    x = pd.DataFrame(columns=['datetime','x','y'])
    df = data.drop('datetime', axis=1)
    # df = ((df.T-df.T.min())/(df.T.max()-df.T.min())).T
    n = len(df)
    m = df.shape[1]
    s = np.array([(np.cos(t), np.sin(t))
                  for t in [2.0 * np.pi * (i / float(m))
                            for i in range(m)]])
    for i in range(n):
        row = df.iloc[i].values
        row_ = np.repeat(np.expand_dims(row, axis=1), 2, axis=1)
        y = (s * row_).sum(axis=0) / row.sum()
        x.loc[i, 'x'] = y[0]
        x.loc[i,'y'] = y[1]
        x.loc[i,'datetime'] = data.loc[i,'datetime']
    return x


code = '000001'
rawD = pd.read_sql(code, eng)
dff = rawD[rawD.datetime >= '2000-01-01'].reset_index(drop=True)
dff['mea'] = (dff.amount/(dff.vol*100)).round(2)
df = dff[['datetime','open','close','high','low','mea','vol','amount']]
eng.dispose()
a = df
# p0 = [[5,13],[13,34]]
p0 = [[5,13]]

#第二个参数n涨幅周期，第三个参数p回测周期。
def GetPCBraw(df,n,p):
    a = (((df.loc[n].close - df.loc[(n-p)].close)/df.loc[(n-p)].close)*100).round(2)
    b = (((df.loc[n].mea - df.loc[(n-p)].mea)/df.loc[(n-p)].mea)*100).round(2)
    return a,b

for n in df.index[::-1]:
    print(n)
    try:
        for p in p0:
            try:
                df.loc[n, 'PCB'+str(p[0])], df.loc[n, 'PCBmea'+str(p[0])]= GetPCBraw(df,n,p[0])
                df.loc[n,'PCB'+str(p[0])+'time'] = df.loc[(n-p[0])].datetime
                df.loc[n,'PCB'+str(p[0])+'time'+str(p[1])] = df.loc[(n-(p[0]+p[1]))].datetime
            except:
                pass
    except:
        pass

df = df.iloc[21:].reset_index(drop=True)
# pcb5 = df[['datetime', 'PCB5','PCBmea5','PCB5time', 'PCB5time13']]
# pcb13 = df[['datetime', 'PCB13','PCBmea13','PCB13time', 'PCB13time34']]

#第二个参数m涨幅周期，第三个参数选择涨幅大于g的记录。
# def GetPCB(pcb,m,g):
#     dd = pd.DataFrame()
#     n = 0
#     while n < len(pcb):
#         try:
#             if pcb[pcb.columns[1]][n:n+m].max() > g :
#                 # print(n)
#                 i = pcb[pcb.columns[1]][n:n+m][pcb[pcb.columns[1]]==pcb[pcb.columns[1]][n:n+m].max()].index.values[0]
#                 n = pcb[pcb.columns[1]][i:i+m][pcb[pcb.columns[1]]==pcb[pcb.columns[1]][i:i+m].max()].index.values[0]
#                 dd = pd.concat([dd,pcb.loc[n].to_frame().T])
#                 n = n + m 
#             else:
#                 n = n + 1
#         except:
#             n = n + 1
#             pass
#     return dd


# df.to_sql('Index0', engAn, if_exists='replace')
#涨幅标注

df.loc[(df.PCB5>=8) & (df.PCB5<11),'clas'] = 1
df.loc[(df.PCB5>=11) & (df.PCB5<15),'clas'] = 2
df.loc[(df.PCB5>=15) & (df.PCB5<21),'clas'] = 3
df.loc[(df.PCB5>=21) & (df.PCB5<25),'clas'] = 4
df.loc[(df.PCB5>=25),'clas'] = 5
b = df.dropna(subset='clas').reset_index(drop=True)

# pcb = [[pcb5,5,8],[pcb5,5,11],[pcb5,5,15],[pcb5,5,21],[pcb5,5,25]]
# for n  in pcb:
#     a = GetPCB(n[0],n[1],n[2]).reset_index(drop=True)
#     a['Num'] = pd.to_datetime(a.datetime)-pd.to_datetime(a.shift(1).datetime)
#     a.set_index('datetime').to_excel('g:/1/2/St'+code + 'PCB'+str(n[1])+'.xlsx')
# df.set_index('datetime').to_excel('g:/1/2/St'+code + '.xlsx')

#生成训练数据PCB参考日前13日
i = 0
qq = pd.DataFrame((a[a.datetime>=b.loc[i][10:12][1]][a.datetime<=b.loc[i][10:12][0]].reset_index()[['open','close','high','low','mea']]).stack().values).T
while i < len(b):
    print(i)
    df = a[a.datetime>=b.loc[i][10:12][1]][a.datetime<=b.loc[i][10:12][0]].reset_index()[['open','close','high','low','mea']]
    aa = pd.DataFrame(df.stack().values).T
    qq = pd.concat([qq,aa])
    i = i + 1

qq = qq[1:].reset_index(drop=True)


qq = ((qq.T-qq.T.min())/(qq.T.max()-qq.T.min())).T
qq['datetime'] = b['PCB5time']

x = rvNorm(qq)