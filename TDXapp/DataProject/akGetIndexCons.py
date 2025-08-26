import akshare as ak
from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')

# IndexLists = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/optIndexs.xlsx', dtype={'IndexCode':object})[['IndexCode','IndexName']].values.tolist()
IndexLists = pd.read_excel('/home/ts/app/TDXapp/tdxAppData/optIndexs.xlsx', dtype={'IndexCode':object})[['IndexCode','IndexName']].values.tolist()

ll = []

df = ak.index_stock_cons(IndexLists[0][0])
df['IndexCode'] = IndexLists[0][0]
df['IndexName'] = IndexLists[0][1] 
for i in IndexLists[1:]:
    try:
        tmp = ak.index_stock_cons(i[0]).drop_duplicates(subset='品种代码',keep='first')
        tmp['IndexCode'] = i[0]
        tmp['IndexName'] = i[1]
        df = pd.concat([df,tmp])
        print(i[0]+'ok !')
    except:
        ll = ll.append(i[0])
        print(i[0]+'EMP !! ')

df.rename(columns={'品种代码':'StockCode', '品种名称':'StockName', '纳入日期':'DP'},inplace=True)

df[['IndexCode', 'IndexName','StockCode', 'StockName', 'DP']].set_index('IndexCode').to_sql('akIndexCons', eng)
pd.DataFrame(ll,columns=['IndexCode']).to_sql('EmpIndex', eng, if_exists='replace')