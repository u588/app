import pandas as pd
from sqlalchemy import create_engine
from sklearn.cluster import DBSCAN
import matplotlib.pyplot as plt
import mplfinance as mpf

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

gm = pd.read_sql('gm', engAn)
engAn.dispose()

gr = gm.groupby('lev4_code')
grList = gr.size().index.to_list()

gr.get_group(grList[0])


code = '600185'
rawD = pd.read_sql(code, eng)
dff = rawD[rawD.datetime >= '2000-01-01'].reset_index(drop=True)
dff['mea'] = (dff.amount/(dff.vol*100)).round(2)
df = dff[['datetime','open','close','high','low','mea','vol','amount']]
eng.dispose()
a = df.copy()
aaa = df.copy()
aaa.loc[:,'date'] = pd.to_datetime(df.datetime)
aaa.set_index('date',inplace=True)

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

#涨幅标注

df.loc[(df.PCB5>=8) & (df.PCB5<11),'label'] = 1
df.loc[(df.PCB5>=11) & (df.PCB5<15),'label'] = 2
df.loc[(df.PCB5>=15) & (df.PCB5<21),'label'] = 3
df.loc[(df.PCB5>=21) & (df.PCB5<25),'label'] = 4
df.loc[(df.PCB5>=25),'label'] = 5
# b = df.dropna(subset='label').reset_index(drop=True)


#生成训练数据PCB参考日前13日 第二个参数m涨幅周期，第三个参数选择涨幅大于g的记录。
def GetPCB(pcb,m,g):
    dd = pd.DataFrame()
    n = 0
    while n < len(pcb):
        try:
            if pcb[pcb.columns[8]][n:n+m].max() >= g :
                # print(n)
                i = pcb[pcb.columns[8]][n:n+m][pcb[pcb.columns[8]]==pcb[pcb.columns[8]][n:n+m].max()].index.values[0]
                n = pcb[pcb.columns[8]][i:i+m][pcb[pcb.columns[8]]==pcb[pcb.columns[8]][i:i+m].max()].index.values[0]
                dd = pd.concat([dd,pcb.loc[n].to_frame().T])
                n = n + m 
            else:
                n = n + 1
        except:
            n = n + 1
            pass
    return dd

# b = GetPCB(df,18,8).reset_index(drop=True)
b = df
# b['num'] = pd.to_datetime(b.datetime)-pd.to_datetime(b.datetime.shift(1))
# b.num.describe()

i = 0
qq = pd.DataFrame((a[(a.datetime>=b.loc[i][10:12][1])&(a.datetime<=b.loc[i][10:12][0])].reset_index()[['open','close','high','low']]).stack().values).T
while i < len(b):
    print(i)
    dfz = a[(a.datetime>=b.loc[i][10:12][1])&(a.datetime<=b.loc[i][10:12][0])].reset_index()[['open','close','high','low']]
    aa = pd.DataFrame(dfz.stack().values).T
    qq = pd.concat([qq,aa])
    i = i + 1

qq = qq[1:].reset_index(drop=True)
qq = ((qq.T-qq.T.min())/(qq.T.max()-qq.T.min())).T
# qq['datetime'] = b['PCB5time']



X = qq.values
model = DBSCAN(eps=0.68 ,min_samples=3)

model.fit(X)

# from numpy import unique
# from numpy import where

yy = model.fit_predict(X)
# clusters = unique(yhat)
# for cluster in clusters:
#     row_ix = where(yhat == cluster)
#     plt.scatter(X[row_ix, 0], X[row_ix, 1])

# plt.show()

b['cluster'] = pd.DataFrame(yy)

xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')
xxg.size()

# #plot
# gg = xxg.get_group(61).sort_values('datetime').reset_index(drop=True)
# n = gg.shape[0]
# i = 0
# fig = mpf.figure()
# while i<n:
#     date = gg.loc[i].PCB5time
#     mpf.plot(aaa[aaa.datetime<=date].tail(14),ax=fig.add_subplot(int(str(n)),2,i*2+1),type='candle',datetime_format="%Y%b%d",ylabel="")
#     mpf.plot(aaa[aaa.datetime>=date].head(6),ax=fig.add_subplot(int(str(n)),2,i*2+2),type='candle',axtitle=str(gg.loc[i].PCB5),datetime_format="%Y%b%d",ylabel="")
#     i  = i+1

# plt.show()


cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()

def glplt(m,v):
    glist= cl[['cluster','count','mean','min','std']].loc[m:v].reset_index(drop=True)
    n = glist.shape[0]
    fig = mpf.figure()
    i = 0
    while i <n :
        gg = xxg.get_group(glist.cluster[i]).head(1)
        date = gg.PCB5time.tolist()[0]
        code = gg.code.tolist()[0]
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime<=date)].tail(9),ax=fig.add_subplot(int(str(n)),2,i*2+1),type='candle',datetime_format="%Y%b%d",ylabel=str(glist['cluster'][i]))
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime>=date)].head(6),ax=fig.add_subplot(int(str(n)),2,i*2+2),type='candle',axtitle=('Mean:'+str(glist['mean'][i])+' Std:'+str(glist['std'][i])),datetime_format="%Y%b%d",ylabel=str(glist['count'][i]))
        i = i + 1
    plt.show()

