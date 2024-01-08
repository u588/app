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
    df.loc[:,'PCB5time13'] = df.datetime.shift(18)
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
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime<=date)].tail(14),ax=fig.add_subplot(int(str(n)),2,i*2+1),type='candle',datetime_format="%Y%b%d",ylabel=code)
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
P=4
List = angr.code.to_list()
codeList = [List[i:i+P] for i in range(0,len(List),P)]
# codeList = angr.code.to_list()[:4]
# codeList = angr[(angr.scale==500)&(angr.b_code==2.0)].code.to_list()



aqq = pd.DataFrame(columns=list(range(56)))
aqa = pd.DataFrame(columns=['code','datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount'])
aqb = pd.DataFrame(columns=['code','datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount','PCB5', 'PCBmea5', 'PCB5time', 'PCB5time13'])

import multiprocessing

if __name__ == '__main__':
    for list in codeList:
        pool  = multiprocessing.Pool(processes=P)
        results = []
        for code in list:
            results.append(pool.apply_async(GetX, (code,) ))
        pool.close()
        pool.join()    
        for res in results:
            aqq = pd.concat([aqq,res.get()[0]])
            aqa = pd.concat([aqa,res.get()[1]])
            aqb = pd.concat([aqb,res.get()[2]])        
        # print(res.get()[2])
    qq = aqq.reset_index(drop=True)
    aaa = aqa.reset_index(drop=True)
    aaa.loc[:,'date'] = pd.to_datetime(aaa.datetime)
    aaa.set_index('date',inplace=True)
    b =aqb.reset_index(drop=True)

    X = qq.values
    model = DBSCAN(eps=0.48,min_samples=5)
    # model = DBSCAN(eps=0.68,min_samples=3)
    model.fit(X)

    yy = model.fit_predict(X)
    b['cluster'] = pd.DataFrame(yy)
    xx = b.sort_values('cluster').reset_index(drop=True)
    xxg = xx.groupby('cluster')
    print(xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False))


#单进程
# def spr(codeList):
#     for code in codeList:    
#         qq,aaa,b = GetX(code)
#         aaa['code']=code
#         b['code']=code
#         aqq = pd.concat([aqq,qq])
#         aqa = pd.concat([aqa,aaa])
#         aqb = pd.concat([aqb,b])

# qq = aqq.reset_index(drop=True)
# aaa = aqa.reset_index(drop=True)
# aaa.loc[:,'date'] = pd.to_datetime(aaa.datetime)
# aaa.set_index('date',inplace=True)
# b =aqb.reset_index(drop=True)

# X = qq.values
# model = DBSCAN(eps=0.48,min_samples=5)
# # model = DBSCAN(eps=0.58,min_samples=5)
# model.fit(X)

# yy = model.fit_predict(X)
# b['cluster'] = pd.DataFrame(yy)
# xx = b.sort_values('cluster').reset_index(drop=True)
# xxg = xx.groupby('cluster')
# xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False)

