# 2026.1.25 tdxGeteBiz 由于'经营分析'模块数据结构改变 转 akshare 

import akshare as ak
from tqdm import tqdm
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text


engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')
engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')

new_mBiz='mBizRAW'+datetime.now().strftime('%Y%m')

# 原表改名为运行月份表
rawmBiz = pd.read_sql('mBizRAW',engB)
rawmBiz.set_index('日期').to_sql(new_mBiz, engB, if_exists='replace')

StockList = pd.read_sql('StocksList', engS)

df = pd.DataFrame()
for n in tqdm(StockList['ts_code'].tolist()):
    try:
        df_tmp = ak.stock_zygc_em(symbol=n[7:]+n[:6])
        df = pd.concat([df, df_tmp])
    except:
        print(n)        
        continue

df.rename(columns={'股票代码':'StockCode'}).to_sql('mBizRAW', engB, if_exists='replace', index=False)
df[df['报告日期']>='2022-12-31'].rename(columns={'股票代码':'StockCode'}).to_sql('mBiz', engB, if_exists='replace', index=False)
        
engS.dispose()
engB.dispose()
