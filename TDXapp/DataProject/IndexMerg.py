import pandas as pd
from sqlalchemy import create_engine


# eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxIndex')
eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')


blk = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsBLK.xlsx', dtype={'IndexCode':object})
cs = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/csIndex.xlsx', dtype={'IndexCode':object})
dpdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/akIndexDP.xlsx', dtype={'IndexCode':object})
numdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/akIndexNum.xlsx', dtype={'IndexCode':object})
zzgz = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxZZGZIndexs.xlsx', dtype={'IndexCode':object})
m3 = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxSHSZIndexs.xlsx', dtype={'IndexCode':object})
dropdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/dropIndexs.xlsx', dtype={'IndexCode':object})
empdf = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/empIndexs.xlsx', dtype={'IndexCode':object})

# sh = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxSHIndexs.xlsx', dtype={'IndexCode':object})
# sz = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxSZIndexs.xlsx', dtype={'IndexCode':object})
# zz = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxZZindexs.xlsx', dtype={'IndexCode':object})

# blk = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxIndexsBLK.xlsx', dtype={'IndexCode':object})
# zz = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxZZIndexs.xlsx', dtype={'IndexCode':object})
# cs = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/csIndex.xlsx', dtype={'IndexCode':object})
# sh = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxSHIndexs.xlsx', dtype={'IndexCode':object})
# sz = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/tdxSZIndexs.xlsx', dtype={'IndexCode':object})



# zz.drop_duplicates(subset='IndexCode',inplace=True)
# m3 = pd.concat([sh, sz])
# m3.reset_index(drop=True, inplace=True)

# blkm = pd.merge(blk,m3.drop(columns='From'), on=['IndexCode','IndexName'],how='inner')
# blkm.reset_index(drop=True, inplace=True)



m3cs = pd.merge(m3,cs[['IndexCode','Num','IndexSTL','DP']], on='IndexCode',how='inner')
m3zz = pd.merge(m3,zzgz['IndexCode'], on='IndexCode',how='inner')
cszz = pd.merge(cs,zzgz[['IndexCode','Market','MarketCode']], on='IndexCode',how='inner')
m3cszz = pd.merge(m3,cszz[['IndexCode','Num','DP','IndexSTL']], on='IndexCode',how='inner')

# df1 = pd.concat([blkm,m3]).drop_duplicates(subset='IndexCode',keep='first')
df1 = pd.concat([blk,m3]).drop_duplicates(subset='IndexCode',keep='first')
df2 = pd.concat([m3cs,df1]).drop_duplicates(subset='IndexCode',keep='first')
df3 = pd.concat([m3zz,df2]).drop_duplicates(subset='IndexCode',keep='first')
df4 = pd.concat([m3cszz,df3]).drop_duplicates(subset='IndexCode',keep='first')
df5 = pd.concat([df4,cszz]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])
df6 = pd.concat([df5,zzgz]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])

dpm = pd.merge(df6[['IndexCode', 'IndexName', 'Market', 'MarketName', 'MarketCode', 'From',
       'Num', 'IndexSTL']],dpdf[['IndexCode','DP']], on='IndexCode',how='inner')
df7 = pd.concat([dpm,df6]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])

mdf = pd.merge(df7[['IndexCode', 'IndexName', 'Market', 'MarketName', 'MarketCode', 'From',
       'DP', 'IndexSTL']],numdf[['IndexCode','Num']], on='IndexCode',how='inner')
df8 = pd.concat([mdf,df7]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode'])

df8.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexs.xlsx')

df9 = pd.concat([df8,dropdf]).drop_duplicates(subset='IndexCode',keep=False).sort_values(by=['IndexCode','MarketCode'])

df9.loc[df9['IndexCode'].isin(empdf['IndexCode']), 'From'] = 'EMP'
df9.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/optIndexs.xlsx')
# df5.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/IndexM.xlsx')

# df5.set_index('IndexCode').to_excel('/home/ts/app/TDXapp/tdxAppData/indexM.xlsx')

# df5.set_index('IndexCode').to_sql('indexM', eng, if_exists='replace')



# zzm = pd.merge(cs,zz, on='IndexCode',how='inner')
# zzm.reset_index(drop=True, inplace=True)

# zm = pd.merge(m3,zzm[['IndexCode','IndexSTL','Num','From','DP']],on=['IndexCode'],how='inner')

# m3zz = pd.concat([zm,zzm]).drop_duplicates(subset='IndexCode',keep='first')
# zzm3 = pd.concat([m3zz,m3]).drop_duplicates(subset='IndexCode',keep='first').reset_index(drop=True)

# finz = pd.concat([blkm,zzm3]).drop_duplicates(subset='IndexCode',keep='first').sort_values(by=['IndexCode','MarketCode']).reset_index(drop=True)
# finz['IndexSTL'] = finz['IndexSTL'].fillna('指数')
# finz['From'] = finz['From'].fillna('TDX')

# finz.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/IndexM.xlsx')

# finz.set_index('IndexCode').to_sql('indexM', eng, if_exists='replace')




# finz = pd.concat([zzm,zm])
# finz.sort_values(by=['IndexCode','MarketCode'],inplace=True)
# finz.drop_duplicates(subset='IndexCode',inplace=True)
# finz.reset_index(drop=True, inplace=True)

# finm = pd.concat([blkm,finz])
# finm.sort_values(by=['IndexCode','MarketCode'],inplace=True)
# finm.drop_duplicates(subset='IndexCode',inplace=True)
# finm.reset_index(drop=True, inplace=True)

# finm.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/IndexM.xlsx')
# finm.set_index('IndexCode').to_excel('/home/ts/app/TDXapp/tdxAppData/indexM.xlsx')

# finm.set_index('IndexCode').to_sql('indexM', eng, if_exists='replace')

print('=========> Merged ! ')