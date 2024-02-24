# pip install adbc_driver_manager adbc_driver_postgresql pyarrow
# pandas 2.2

import adbc_driver_postgresql.dbapi as pg_dbapi

uri = "postgresql://sa:11111111@10.3.18.56:5432/DataAn"
conn = pg_dbapi.connect(uri)
pd.read_sql('gm', conn)


import pandas as pd
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
import mplfinance as mpf
import datetime

engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')
engAn = create_engine('postgresql+psycopg2://sa:11111111@111.61.77.88:65123/DataAn')

# nm聚类编号
def gplt(nm,m=0,v=5):
    gg = xxg.get_group(nm).sort_values('datetime').reset_index(drop=True).loc[m:v].reset_index(drop=True)
    n = gg.shape[0]
    i = 0
    fig = mpf.figure()
    while i<n:
        date = gg.loc[i].PCB5time
        code = gg.loc[i].code
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime<=date)].tail(9),ax=fig.add_subplot(int(str(n)),2,i*2+1),type='candle',datetime_format="%Y.%m.%d",ylabel=code)
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime>=date)].head(6),ax=fig.add_subplot(int(str(n)),2,i*2+2),type='candle',axtitle=str(nm),datetime_format="%Y.%m.%d",ylabel=str(gg.loc[i].PCB5),style='classic')
        i  = i+1
    plt.show()

def glplt(cl,m=0,v=8):
    glist= cl[['cluster','count','mean','min','std']].loc[m:v].reset_index(drop=True)
    n = glist.shape[0]
    fig = mpf.figure()
    i = 0
    while i <n :
        gg = xxg.get_group(glist.cluster[i]).head(1)
        date = gg.PCB5time.tolist()[0]
        code = gg.code.tolist()[0]
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime<=date)].tail(9),ax=fig.add_subplot(int(str(n)),2,i*2+1),type='candle',datetime_format="%Y.%m.%d",ylabel=str(glist['cluster'][i]))
        mpf.plot(aaa[(aaa.code==code)&(aaa.datetime>=date)].head(6),ax=fig.add_subplot(int(str(n)),2,i*2+2),type='candle',axtitle=('Mean:'+str(glist['mean'][i])+' Std:'+str(glist['std'][i])),datetime_format="%Y.%m.%d",ylabel=str(glist['count'][i]))
        i = i + 1
    plt.show()

def cplt(code,day):
    mpf.plot(aaa[(aaa.code==code)&(aaa.index <(pd.to_datetime(day)+datetime.timedelta(days=15))) \
                 &(aaa.index >(pd.to_datetime(day)-datetime.timedelta(days=28)))],type='candle',datetime_format="%Y.%m.%d",ylabel=code)
    plt.show()


li =[[300,1],[300,2],[500,1],[500,2],[1000,1],[1000,2],[2000,1],[2000,2]]

gml = li[0]
esp = 0.37 

b = pd.read_sql(('b'+str(gml[0]) + str(gml[1])+'e'+str(esp)+'s8'), engAn)
b['Dday'] = (pd.to_datetime(b['datetime']) - pd.to_datetime(b['PCB5time8'])).dt.days

aaa = pd.read_sql('b'+str(gml[0]) + str(gml[1]), engAn)
aaa.loc[:,'date'] = pd.to_datetime(aaa.datetime)
aaa.set_index('date',inplace=True)

xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')

cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()
ccl = cl[(cl['count']>5) & (cl['25%']>6)].reset_index(drop=True)


#查看聚类在gm中的详情
gm = pd.read_sql('gm', engAn)
engAn.dispose()
gm[gm['code'].isin(b[b['cluster']==19]['code'].tolist())]

# 计算时间跨度
gmm = xxg.get_group(21)
pd.to_datetime(gmm['datetime']) - pd.to_datetime(gmm['PCB5time8'])