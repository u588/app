import pandas as pd
from sqlalchemy import create_engine


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxIndex')


blk = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsBLK.xlsx', dtype={'IndexCode':object})
zz = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxZZindexs.xlsx', dtype={'IndexCode':object})
cs = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/csIndex.xlsx', dtype={'IndexCode':object})
sh = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxSHIndexs.xlsx', dtype={'IndexCode':object})
sz = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxSZIndexs.xlsx', dtype={'IndexCode':object})

zz.drop_duplicates(subset='IndexCode',inplace=True)
m3 = pd.concat([sh, sz])
m3.reset_index(drop=True, inplace=True)

blkm = pd.merge(blk,m3, on=['IndexCode','IndexName'],how='inner')
blkm.reset_index(drop=True, inplace=True)
zzm = pd.merge(cs,zz, on='IndexCode',how='inner')
zzm.reset_index(drop=True, inplace=True)

zm = pd.merge(m3,zzm[['IndexCode','IndexSTL','Num','From']],on=['IndexCode'],how='inner')
finz = pd.concat([zzm,zm])
finz.sort_values(by=['IndexCode','MarketCode'],inplace=True)
finz.drop_duplicates(subset='IndexCode',inplace=True)
finz.reset_index(drop=True, inplace=True)

finm = pd.concat([blkm,finz])
finm.sort_values(by=['IndexCode','MarketCode'],inplace=True)
finm.drop_duplicates(subset='IndexCode',inplace=True)
finm.reset_index(drop=True, inplace=True)

finm.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/IndexM.xlsx')

print('=========> Merged ! ')