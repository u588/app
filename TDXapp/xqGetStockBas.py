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
 

