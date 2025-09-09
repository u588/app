import pandas as pd
from datetime import datetime

current_date = datetime.now().strftime("%Y-%m-%d") 

dqdf = pd.read_csv('D:/new_tdx/T0002/export/地区板块.txt',sep=',',dtype='object',encoding='gb18030',encoding_errors='replace',header=None,names=['IndexCode','IndexName','StockCode','StockName'])
dqdf['IndexSTL'] = '地区'

fgdf = pd.read_csv('D:/new_tdx/T0002/export/风格板块.txt',sep=',',dtype='object',encoding='gb18030',encoding_errors='replace',header=None,names=['IndexCode','IndexName','StockCode','StockName'])
fgdf['IndexSTL'] = '风格'

gndf = pd.read_csv('D:/new_tdx/T0002/export/概念板块.txt',sep=',',dtype='object',encoding='gb18030',encoding_errors='replace',header=None,names=['IndexCode','IndexName','StockCode','StockName'])
gndf['IndexSTL'] = '概念'

hy80df = pd.read_csv('D:/new_tdx/T0002/export/行业板块80.txt',sep=',',dtype='object',encoding='gb18030',encoding_errors='replace',header=None,names=['IndexCode','IndexName','StockCode','StockName'])
hy80df['IndexSTL'] = '行业'

hy81df = pd.read_csv('D:/new_tdx/T0002/export/行业板块81.txt',sep=',',dtype='object',encoding='gb18030',encoding_errors='replace',header=None,names=['IndexCode','IndexName','StockCode','StockName'])
hy81df['IndexSTL'] = '行业'

icdf = pd.concat([dqdf,gndf,fgdf,hy81df,hy80df])
icdf['DP'] = current_date


iiRaw = icdf[['IndexCode','IndexName','IndexSTL','DP']].drop_duplicates(subset='IndexCode').drop_duplicates(subset='IndexName',keep='first').reset_index(drop=True)

Numdf = icdf['IndexCode'].value_counts().reset_index().rename(columns={'count':'Num'})

iidf = pd.merge(iiRaw,Numdf,on='IndexCode',how='inner')
iidf['Market'] = 'ST'
iidf['MarketName'] = 'TDXBLK'
iidf['MarketCode'] = 1
iidf['From'] = 'TDXBLK'

iidf.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsBLK.xlsx')
icdf[icdf['IndexCode'].isin(iidf['IndexCode'])].sort_values(by = ['IndexCode', 'StockCode'],ascending=True,ignore_index=True).set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsConsBLK.xlsx')

print('Saved  ok !')