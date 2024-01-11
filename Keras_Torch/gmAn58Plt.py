from sklearn.cluster import DBSCAN

import pandas as pd
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
import mplfinance as mpf

engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

def gplt(nm,m,v):
    gg = xxg.get_group(nm).sort_values('datetime').reset_index(drop=True).loc[m:v].reset_index(drop=True)
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


def glplt(cl,m,v):
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


fname = '5001'
eps = 'e0.14s3b'


b = pd.read_sql((eps+fname), engAn)
aaa = pd.read_sql(('aaa'+fname), engAn)
aaa.loc[:,'date'] = pd.to_datetime(aaa.datetime)
aaa.set_index('date',inplace=True)

xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')
xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).reset_index()
cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()

