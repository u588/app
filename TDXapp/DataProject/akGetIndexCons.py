import akshare as ak
from sqlalchemy import create_engine
import pandas as pd
import time
import random


eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')

rawD = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/optIndexs.xlsx', dtype={'IndexCode':object})
# rawD = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/optIndexs.xlsx', dtype={'IndexCode':object})

IndexLists = rawD[~rawD['From'].isin(['TDXBLK','EMP'])][['IndexCode','IndexName','IndexSTL']].values.tolist()
random.shuffle(IndexLists)
ll = []

df = pd.DataFrame(columns=['品种代码', '品种名称', '纳入日期','IndexCode','IndexName','IndexSTL'], dtype=object)
for n,i in enumerate(IndexLists):
    if (n+1) % 300 == 0:
        # delay = random.uniform(300,305)
        delay = random.uniform(10,20)
        print(f"触发延时: {delay:.2f}秒")
        time.sleep(delay)        
    try:
        tmp = ak.index_stock_cons(i[0]).drop_duplicates(subset='品种代码',keep='first')
        tmp['IndexCode'] = i[0]
        tmp['IndexName'] = i[1]
        tmp['IndexSTL'] = i[2]
        df = pd.concat([df,tmp])
        print(i[0]+'ok !')
        # time.sleep(random.uniform(0, 3))
    except:
        ll.append(i[0])
        print(i[0]+'EMP !! ')

df.rename(columns={'品种代码':'StockCode', '品种名称':'StockName', '纳入日期':'DP'},inplace=True)

df.set_index('IndexCode').to_sql('akIndexCons', eng, if_exists='replace')
print('to_sql OK !')

pd.DataFrame(ll,columns=['IndexCode']).to_excel('G:/Gitee/App/TDXapp/tdxAppData/akEMP.xlsx')
pd.DataFrame(ll,columns=['IndexCode']).to_excel('G:/Gitee/App/TDXapp/tdxAppData/akEMPB.xlsx')
# pd.DataFrame(ll,columns=['IndexCode']).to_excel('/home/ts/app/TDXapp/tdxAppData/akEMP.xlsx')
# pd.DataFrame(ll,columns=['IndexCode']).to_excel('/home/ts/app/TDXapp/tdxAppData/akEMPB.xlsx')