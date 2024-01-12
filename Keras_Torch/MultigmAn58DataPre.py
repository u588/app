import pandas as pd
from sqlalchemy import create_engine
from sklearn.cluster import DBSCAN

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

def GetX(code):
    rawD = pd.read_sql(code, eng)
    dff = rawD[rawD.datetime >= '2000-01-01'].reset_index(drop=True)
    dff['mea'] = (dff.amount/(dff.vol*100)).round(2)
    df = dff[['datetime','open','close','high','low','mea','vol','amount']]
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
    qq = pd.DataFrame(columns=list(range(36)))
    while i < len(b):
        print(i)
        dfz = a[(a.datetime>=b.loc[i][10:12][1])&(a.datetime<=b.loc[i][10:12][0])].reset_index()[['open','close','high','low']]
        aa = pd.DataFrame(dfz.stack().values).T
        qq = pd.concat([qq,aa])
        i = i + 1
    qq = qq.reset_index(drop=True)
    qq = ((qq.T-qq.T.min())/(qq.T.max()-qq.T.min())).T
    return qq,aaa,b

gm = pd.read_sql('gm', engAn)
engAn.dispose()


#数据分成进程数P
# codeList = angr.code.to_list()[9:19]
# codeList = angr[(angr.scale==500)&(angr.b_code==2.0)].code.to_list()
P=8
filname = '3001'
List = gm[(gm['scale']==300)&(gm['b_code']==1)].code.tolist()
codeList = [List[i:i+P] for i in range(0,len(List),P)]


aqq = pd.DataFrame(columns=list(range(36)))
aqa = pd.DataFrame(columns=['datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount','code'])
aqb = pd.DataFrame(columns=['datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount','PCB5', 'PCBmea5', 'PCB5time', 'PCB5time8','code'])

import multiprocessing

if __name__ == '__main__':
    for list in codeList:

        for code in list:
            pool  = multiprocessing.Pool(processes=P)            
            results = []
            results.append(pool.apply_async(GetX, (code,) ))
            aqq = pd.concat([aqq,results[0].get()[0]])
            a = results[0].get()[1]
            a['code'] = code
            aqa = pd.concat([aqa,a])
            b = results[0].get()[2]
            b['code'] = code
            aqb = pd.concat([aqb,b])       
            pool.close()
            pool.join()    
    
    qq = aqq.reset_index(drop=True)
    aaa = aqa.reset_index(drop=True)
    # aaa.loc[:,'date'] = pd.to_datetime(aaa.datetime)
    # aaa.set_index('date',inplace=True)
    b =aqb.reset_index(drop=True)
    qq.set_index(0).to_sql(('qq'+filname),engAn, if_exists='replace')
    aaa.set_index('code').to_sql(('aaa'+filname),engAn, if_exists='replace')
    b.set_index('code').to_sql(('b'+filname),engAn, if_exists='replace')

    X = qq.fillna(1).values

# ============ minSamples 3
    esp = 0.19
    n = 200
    while n > 100 :
        model = DBSCAN(eps=esp,min_samples=3)
        print('fit ESP:'+str(esp))
        yy = model.fit_predict(X)
        n = pd.DataFrame(yy).groupby(0).size().shape[0]
        print(n)
        b['cluster'] = pd.DataFrame(yy)
        b.set_index('code').to_sql(('e'+str(esp)+'s3b'+filname),engAn, if_exists='replace')
        xx = b.sort_values('cluster').reset_index(drop=True)
        xxg = xx.groupby('cluster')
        xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).reset_index()

        cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()
        cl.to_sql(('e'+str(esp)+'s3bcl'+filname),engAn, if_exists='replace')
        if n > 500:
            esp = round(esp-0.05 , 2)
        else:
            esp = round(esp-0.02, 2)


#=========== minSamples 5
    esp = 0.22
    n = 300
    while n > 120 :
        model = DBSCAN(eps=esp,min_samples=5)
        print('fit ESP:'+str(esp))
        yy = model.fit_predict(X)
        n = pd.DataFrame(yy).groupby(0).size().shape[0]
        print(n)
        b['cluster'] = pd.DataFrame(yy)
        b.set_index('code').to_sql(('e'+str(esp)+'s5b'+filname),engAn, if_exists='replace')
        xx = b.sort_values('cluster').reset_index(drop=True)
        xxg = xx.groupby('cluster')
        xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).reset_index()

        cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()
        cl.to_sql(('e'+str(esp)+'s5bcl'+filname),engAn, if_exists='replace')
        if n > 500:
            esp = round(esp-0.05, 2)
        else:
            esp = round(esp-0.02 , 2)