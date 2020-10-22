import requests
from sqlalchemy import create_engine
import datetime
import numpy as np
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/smDaily')
header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}

# def getFina(stockID):

url = 'http://www.csindex.com.cn/uploads/downloads/other/files/zh_CN/Index_Information.xls'
r = requests.get(url, headers=header)
a = pd.read_excel(r.content,index_col=None, header=None,skiprows=1)
date = a.iloc[0][0]
date = date[1:5]+'-'+date[6:8]+'-'+date[9:11]
gz = a.loc[2:13].fillna('指数')
gz.columns = gz.loc[2]
gzh = pd.read_excel('/home/ts/app/in.xls')
m = pd.concat([gzh,gz], ignore_index=True)
m.columns= m.loc[0]
m.drop(0,inplace=True)
m.drop(1,inplace=True)
m['date']=date
m.set_index('date',inplace=True)
m.to_sql('Market',eng, if_exists='append')
print('Market Saved !')

hs = a.loc[17:26]
hs300 = hs[[0,1,2,3]].reset_index(drop=True)
hs300.columns= ['code','close','pct_chg','contrib']
hs300['date'] = date
hs300.set_index('date').to_sql('hs300',eng,if_exists='append')
print('hs300 Saved !')

zz500 = hs[[5,6,7,8]].reset_index(drop=True)
zz500.columns= ['code','close','pct_chg','contrib']
zz500['date'] = date
zz500.set_index('date').to_sql('zz500',eng,if_exists='append')
print('zz500 Saved !')

sz50 = hs[[10,11,12,13]].reset_index(drop=True)
sz50.columns= ['code','close','pct_chg','contrib']
sz50['date'] = date
sz50.set_index('date').to_sql('sz50',eng,if_exists='append')
print('sz50 Saved !')

sh = a.loc[30:34].dropna(axis=1)
sh[6] = 'sh'
sz = a.loc[38:42].dropna(axis=1)
sz[6] = 'sz'

Strong = pd.concat([sh[[0,2,6]],sz[[0,2,6]]],ignore_index=True)
Strong.columns = ['code', 'pct_chg','exchange']
Strong['date'] = date
Strong.set_index('date').to_sql('Strong',eng,if_exists='append')
print('Strong Saved !')

weak = pd.concat([sh[[3,5,6]],sz[[3,5,6]]],ignore_index=True)
weak.columns = ['code', 'pct_chg','exchange']
weak['date'] = date
weak.set_index('date').to_sql('weak',eng,if_exists='append')
print('weak Saved !')