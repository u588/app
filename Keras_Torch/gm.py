import pandas as pd
from sqlalchemy import create_engine
import numpy as np

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

gm = pd.read_sql('gm', engAn)
engAn.dispose()

gr = gm.groupby('lev4_code')
grList = gr.size().index.to_list()

gr.get_group(grList[0])


code = '601600'
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

df.loc[(df.PCB5>=8) & (df.PCB5<11),'clas'] = 1
df.loc[(df.PCB5>=11) & (df.PCB5<15),'clas'] = 2
df.loc[(df.PCB5>=15) & (df.PCB5<21),'clas'] = 3
df.loc[(df.PCB5>=21) & (df.PCB5<25),'clas'] = 4
df.loc[(df.PCB5>=25),'clas'] = 5
b = df.dropna(subset='clas').reset_index(drop=True)


#生成训练数据PCB参考日前13日
i = 0
qq = pd.DataFrame((a[a.datetime>=b.loc[i][10:12][1]][a.datetime<=b.loc[i][10:12][0]].reset_index()[['open','close','high','low']]).stack().values).T
while i < len(b):
    print(i)
    dfz = a[a.datetime>=b.loc[i][10:12][1]][a.datetime<=b.loc[i][10:12][0]].reset_index()[['open','close','high','low']]
    aa = pd.DataFrame(dfz.stack().values).T
    qq = pd.concat([qq,aa])
    i = i + 1

qq = qq[1:].reset_index(drop=True)


qq = ((qq.T-qq.T.min())/(qq.T.max()-qq.T.min())).T
qq['datetime'] = b['PCB5time']


from sklearn.cluster import DBSCAN
from numpy import unique
from numpy import where
import matplotlib.pyplot as plt
import mplfinance as mpf


X = qq.values
model = DBSCAN(eps=0.7 ,min_samples=3)

model.fit(X)
yhat = model.fit_predict(X)
clusters = unique(yhat)
for cluster in clusters:
    row_ix = where(yhat == cluster)
    plt.scatter(X[row_ix, 0], X[row_ix, 1])

plt.show()

b['clus'] = pd.DataFrame(yhat)

xx = b.sort_values('clus').reset_index(drop=True)
xxg = xx.groupby('clus')
xxg.size()
gg = xxg.get_group(4).reset_index(drop=True)

n = gg.shape[0]
i = 0
fig = mpf.figure()
while i<n:
    date = gg.loc[i].PCB5time
    mpf.plot(aaa[aaa.datetime<=date].tail(14),ax=fig.add_subplot(int(str(n)),2,i*2+1),type='candle')
    mpf.plot(aaa[aaa.datetime>=date].head(6),ax=fig.add_subplot(int(str(n)),2,i*2+2),type='candle',axtitle=str(gg.loc[i].PCB5))
    i  = i+1

plt.show()


