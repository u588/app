import pandas as pd
from sqlalchemy import create_engine
from sklearn.cluster import DBSCAN
import matplotlib.pyplot as plt
import mplfinance as mpf

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

def GetX(code):
    rawD = pd.read_sql(code, eng)
    dff = rawD[rawD.datetime >= '2000-01-01'].reset_index(drop=True)
    dff['mea'] = (dff.amount/(dff.vol*100)).round(2)
    df = dff[['datetime','open','close','high','low','mea','vol','amount']]
    eng.dispose()
    df = df.copy()
    a = df.copy()
    aaa = df.copy()
    df.loc[:,'PCB5'] = (df.close.pct_change(5)*100).round(2)
    df.loc[:,'PCBmea5'] = (df.mea.pct_change(5)*100).round(2)
    df.loc[:,'PCB5time'] = df.datetime.shift(5)
    df.loc[:,'PCB5time8'] = df.datetime.shift(13)
    df = df.iloc[21:].reset_index(drop=True)
    b = df
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
    return qq,aaa,b

def gplt(clum):
    gg = xxg.get_group(clum).sort_values('datetime').reset_index(drop=True)
    n = gg.shape[0]
    i = 0
    fig = mpf.figure()
    while i<n:
        date = gg.loc[i].PCB5time
        code = gg.loc[i].code
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime<=date)].tail(9),ax=fig.add_subplot(int(str(n)),2,i*2+1),type='candle',datetime_format="%Y%b%d",ylabel=code)
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime>=date)].head(6),ax=fig.add_subplot(int(str(n)),2,i*2+2),type='candle',axtitle=str(gg.loc[i].PCB5),datetime_format="%Y%b%d",ylabel="")
        i  = i+1
    plt.show()

gm = pd.read_sql('gm', engAn)
engAn.dispose()

gr = gm.groupby('lev4_code')
grList = gr.size().index.to_list()

# angr = gr.get_group(grList[243])
angr = gr.get_group(55102010)

#数据分成进程数P
codeList = angr.code.to_list()[9:19]
# codeList = angr[(angr.scale==500)&(angr.b_code==2.0)].code.to_list()
# codeList = gm[(gm['scale']==1000)&(gm['b_code']==2)].code.tolist()



aqq = pd.DataFrame(columns=list(range(36)))
aqa = pd.DataFrame(columns=['datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount','code'])
aqb = pd.DataFrame(columns=['datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount','PCB5', 'PCBmea5', 'PCB5time', 'PCB5time8','code'])


for code in codeList:    
    qq,aaa,b = GetX(code)
    aaa['code']=code
    b['code']=code
    aqq = pd.concat([aqq,qq])
    aqa = pd.concat([aqa,aaa])
    aqb = pd.concat([aqb,b])

qq = aqq.reset_index(drop=True)
aaa = aqa.reset_index(drop=True)
aaa.loc[:,'date'] = pd.to_datetime(aaa.datetime)
aaa.set_index('date',inplace=True)
b =aqb.reset_index(drop=True)

X = qq.fillna(1).values
# minSamples 3
e = 0.19
n = 200
while n > 100 :
    model = DBSCAN(eps=e,min_samples=3)
    print('fit ESP:'+str(esp))
    yy = model.fit_predict(X)
    n = pd.DataFrame(yy).groupby(0).size().shape[0]
    print(n)
    esp = esp - 0.02

# minSamples 5
e = 0.27
n = 300
while n > 200 :
    model = DBSCAN(eps=e,min_samples=5)
    print('fit ESP:'+str(esp))
    yy = model.fit_predict(X)
    n = pd.DataFrame(yy).groupby(0).size().shape[0]
    print(n)
    esp = esp - 0.02


#参数规范 25%>8  model数量100左右
    #esp 0.27 s5
    #esp 0.19 s3

#========= 60万记录 300 175标的=== 
#model = DBSCAN(eps=0.28,min_samples=5)
#573
#model = DBSCAN(eps=0.26,min_samples=5)
#

#model = DBSCAN(eps=0.18,min_samples=3)
#162
#model = DBSCAN(eps=0.16,min_samples=3)
#95

#========= 240万记录 10001 680标的 ==

#========= 43万记录 10002 320标的===
#model = DBSCAN(eps=0.28,min_samples=5)
#286 17 相似度不高
#model = DBSCAN(eps=0.27,min_samples=5)
#218 17 相似度不高

#model = DBSCAN(eps=0.244,min_samples=5)
#90 6 

#model = DBSCAN(eps=0.19,min_samples=3)
#100 10 
#model = DBSCAN(eps=0.186,min_samples=3)
#95 11 
#model = DBSCAN(eps=0.18,min_samples=3)
#77 10 
#model = DBSCAN(eps=0.16,min_samples=3)
#54  8 




model.fit(X)

yy = model.fit_predict(X)
b['cluster'] = pd.DataFrame(yy)
xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')
xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).reset_index()

cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()

def glplt(df,m,v):
    glist= df[['cluster','count','mean','min','std']].loc[m:v].reset_index(drop=True)
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


