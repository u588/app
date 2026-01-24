import akshare as ak
from sqlalchemy import create_engine
import pandas as pd
from tqdm import tqdm
import numpy as np


engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')

StockList = pd.read_sql('StocksList', engS)


ls = []
for n in tqdm(StockList['ts_code'].tolist()):
    try:
        dfs = ak.stock_individual_spot_xq(symbol=n[7:]+n[:6])
        ls.append(dfs)
    except:
        continue
rows = []
for df in ls:
    # 将 item-value 转为 dict，再转为 Series 或 dict
    row = df.set_index('item')['value'].to_dict()
    rows.append(row)

# 合并为新 DataFrame
result = pd.DataFrame(rows)
 
df = result[['代码', '名称','52周最高', '52周最低', '昨收','均价', '今年以来涨幅','每股收益',  '每股净资产','流通股','流通值', '基金份额/总股本', '资产净值/总市值','净资产中的商誉', '市盈率(动)','市净率', '市盈率(TTM)','市盈率(静)','股息(TTM)','股息率(TTM)',  '发行日期', '时间']].rename(columns={'名称':'StockName',})
col = df.columns.tolist()
df['StockCode']= df['代码'].str[2:]
df[['StockCode']+col[1:]].to_sql('xqStockBas', engB,if_exists='replace',index=False)