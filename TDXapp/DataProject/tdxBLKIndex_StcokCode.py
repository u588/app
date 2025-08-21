import re
import pandas as pd
from datetime import datetime

current_date = datetime.now().strftime("%Y-%m-%d") 

dq = open('D:/new_tdx/T0002/export/地区板块.txt', 'r',encoding="GBK", errors='ignore').read()
fg = open('D:/new_tdx/T0002/export/风格板块.txt', 'r',encoding="GBK", errors='ignore').read()
gn = open('D:/new_tdx/T0002/export/概念板块.txt', 'r',encoding="GBK", errors='ignore').read()
hy = open('D:/new_tdx/T0002/export/行业板块.txt', 'r',encoding="GBK", errors='ignore').read()
# zs = open('D:/new_tdx/T0002/export/指数板块.txt', 'r',encoding="GBK", errors='ignore').read()


dfi = pd.DataFrame(columns=['IndexCode', 'IndexName', 'StockCode', 'StockName','IndexSTL'])
dfs = pd.DataFrame(columns=['IndexCode', 'IndexName','IndexSTL', 'Num', 'From'])

def getCons(data, STL):
    dfi = pd.DataFrame(columns=['IndexCode', 'IndexName', 'StockCode', 'StockName','IndexSTL'])
    l = data.replace('\n','#').split('#')
    n = 0
    while n < len(l)-1:
        dfl = pd.DataFrame(l[n].split(',')).T
        dfl.columns=['IndexCode', 'IndexName', 'StockCode', 'StockName']
        dfi = pd.concat([dfi, dfl])
        n = n + 1
    dfi['IndexSTL'] = STL
    dfi.reset_index(drop=True, inplace=True)
    return dfi

# data = [[dq,'地区'],[fg, '风格'], [gn, '概念'], [hy, '行业'], [zs, '指数']]
data = [[dq,'地区'],[fg, '风格'], [gn, '概念'], [hy, '行业']]

dfi = pd.DataFrame(columns=['IndexCode', 'IndexName', 'StockCode', 'StockName','IndexSTL'])
for i in data:
    df = getCons(i[0], i[1])
    print(i[1] + 'ok ! ')
    dfi = pd.concat([dfi, df])

dfi.sort_values(by = ['IndexCode', 'StockCode'],ascending=True,ignore_index=True)\
    .set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsConsBLK.xlsx')

dfs = dfi[['IndexCode','IndexName','IndexSTL']].drop_duplicates().reset_index(drop=True)
n = 0
while n < dfs.shape[0]:
    dfs.loc[n,'Num'] = len(dfi.groupby('IndexCode').groups[dfs.iloc[n,0]])
    n = n + 1
    # print(str(n) + '  ok !')


# dfs['Num'] = dfi.groupby('IndexCode').count()['IndexName'].reset_index(drop=True)
dfs['From'] = 'TDXBLK'
dfs['DP'] = current_date
dfs.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxIndexsBLK.xlsx')
print('Saved  ok !')