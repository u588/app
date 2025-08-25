from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API
import pandas as pd

eapi =  TdxExHq_API()
api = TdxHq_API()

eapi.connect('47.112.95.207', 7720)

mcount = int(eapi.get_instrument_count()/1000)

df = api.to_df(eapi.get_instrument_info(start=0,count=1000))
i = 1
while i<=mcount :
    df1 = api.to_df(eapi.get_instrument_info(start=i*1000,count=1000))
    df = pd.concat([df,df1])
    i = i + 1

zzdf = df[df['market']==62][['code','name']].rename(columns={'code':'IndexCode','name':'IndexName'}).reset_index(drop=True)
zzdf['Market']='EX'
zzdf['MarketCode'] = 62

gzdf = df[df['market']==102][['code','name']].rename(columns={'code':'IndexCode','name':'IndexName'}).reset_index(drop=True)
gzdf['Market'] = 'EX'
gzdf['MarketCode'] = 102
zzgz = pd.concat([zzdf, gzdf]).set_index('IndexCode')
zzgz.to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxZZGZIndexs.xlsx')
print('OK !')