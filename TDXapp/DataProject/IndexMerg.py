import pandas as pd
from sqlalchemy import create_engine


# eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxIndex')
eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')


blk = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsBLK.xlsx', dtype={'IndexCode':object})
cs = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/csIndex.xlsx', dtype={'IndexCode':object})
dpdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/akIndexDP.xlsx', dtype={'IndexCode':object})
cnidf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/cniGzSzIndexs.xlsx', dtype={'IndexCode':object})
zzgz = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxApiZzGzIndexs.xlsx', dtype={'IndexCode':object})
m3 = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxShSzIndexs.xlsx', dtype={'IndexCode':object})

# blk = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxIndexsBLK.xlsx', dtype={'IndexCode':object})
# zz = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxZZIndexs.xlsx', dtype={'IndexCode':object})
# cs = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/csIndex.xlsx', dtype={'IndexCode':object})
# sh = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxSHIndexs.xlsx', dtype={'IndexCode':object})
# sz = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxSZIndexs.xlsx', dtype={'IndexCode':object})

m3cs = pd.merge(m3.drop('MarketName',axis=1),cs[['IndexCode','MarketName','Num','IndexSTL','DP']], on='IndexCode',how='inner')
m3zz = pd.merge(m3.drop('MarketName',axis=1),zzgz[['IndexCode','MarketName']], on='IndexCode',how='inner')
cszz = pd.merge(cs,zzgz[['IndexCode','Market','MarketCode']], on='IndexCode',how='inner')
m3cszz = pd.merge(m3.drop('MarketName',axis=1),cszz[['IndexCode','MarketName','Num','DP','IndexSTL']], on='IndexCode',how='inner')

df1 = pd.concat([blk,m3]).drop_duplicates(subset='IndexCode',keep='first')
df2 = pd.concat([m3cs,df1]).drop_duplicates(subset='IndexCode',keep='first')
df3 = pd.concat([m3zz,df2]).drop_duplicates(subset='IndexCode',keep='first')
df4 = pd.concat([m3cszz,df3]).drop_duplicates(subset='IndexCode',keep='first')
df5 = pd.concat([df4,cszz]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])
df6 = pd.concat([df5,zzgz]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])

dpm = pd.merge(df6[['IndexCode', 'IndexName', 'Market', 'MarketName', 'MarketCode', 'From',
       'Num', 'IndexSTL']],dpdf[['IndexCode','DP']], on='IndexCode',how='inner')
df7 = pd.concat([dpm,df6]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])

mdf = pd.merge(df7[['IndexCode', 'IndexName', 'Market', 'MarketName', 'MarketCode',
       'DP','From']],cnidf[['IndexCode','Num', 'IndexSTL']], on='IndexCode',how='inner')
df8 = pd.concat([mdf,df7]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])

df8.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexs.xlsx')

print('=========> Merged ! ')