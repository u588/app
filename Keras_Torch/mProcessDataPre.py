import pandas as pd
from sqlalchemy import create_engine
import datetime

def GetX(code):
    eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
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
        # print(i)
        dfz = a[(a.datetime>=b.loc[i][10:12][1])&(a.datetime<=b.loc[i][10:12][0])].reset_index()[['open','close','high','low']]
        aa = pd.DataFrame(dfz.stack().values).T
        qq = pd.concat([qq,aa])
        i = i + 1
    qq = qq.reset_index(drop=True)
    qq = ((qq.T-qq.T.min())/(qq.T.max()-qq.T.min())).T
    eng.dispose()
    return qq,aaa,b

engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')
gm = pd.read_sql('gm', engAn)
engAn.dispose()


#数据分成进程数P
# codeList = angr.code.to_list()[9:19]
# codeList = angr[(angr.scale==500)&(angr.b_code==2.0)].code.to_list()
P=30
gmli =[[300,1],[300,2],[500,1],[500,2],[1000,1],[1000,2],[2000,1],[2000,2]]

for List in gmli:
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    gmcodeList = gm[(gm['scale']==List[0])&(gm['b_code']==List[1])].code.tolist()
    codeList = [gmcodeList[i:i+P] for i in range(0,len(gmcodeList),P)]
    filname = str(List[0]) + str(List[1])

    aqq = pd.DataFrame(columns=list(range(36)))
    aqa = pd.DataFrame(columns=['datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount','code'])
    aqb = pd.DataFrame(columns=['datetime', 'open', 'close', 'high', 'low', 'mea', 'vol', 'amount','PCB5', 'PCBmea5', 'PCB5time', 'PCB5time8','code'])

    from  concurrent.futures import ProcessPoolExecutor

    for li in codeList:
        with ProcessPoolExecutor(max_workers=P) as executor:
            fu = [executor.submit(GetX,code) for code in li]
        for i in range(len(li)):
            aqq = pd.concat([aqq,fu[i].result()[0]])
            a = fu[i].result()[1]
            a['code'] = li[i]
            aqa = pd.concat([aqa,a])
            b = fu[i].result()[2]
            b['code'] = li[i]
            aqb = pd.concat([aqb,b])
            

    qq = aqq.reset_index(drop=True)
    qq = qq.iloc[:,:36]
    aaa = aqa.reset_index(drop=True)
    aaa.loc[:,'date'] = pd.to_datetime(aaa.datetime)
    aaa.set_index('date',inplace=True)
    b =aqb.reset_index(drop=True)

    engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')
    qq.set_index(0).to_sql(('qq'+filname),engAn, if_exists='replace')
    aaa.set_index('code').to_sql(('aaa'+filname),engAn, if_exists='replace')
    b.set_index('code').to_sql(('b'+filname),engAn, if_exists='replace')
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print(filname+': slq Saved !!')

    engAn.dispose()



    executor.shutdown()
