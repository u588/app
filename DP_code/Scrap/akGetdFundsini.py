
from sqlalchemy import create_engine
import pandas as pd
import akshare as ak

from tqdm import tqdm
import time
import random

engDF = create_engine('postgresql+psycopg://sa:11111111@10.145.254.56:5432/dFunds')
engS = create_engine('postgresql+psycopg://sa:11111111@10.145.254.56:5432/tdxStocks')

StockLists = pd.read_sql('StocksList', engS).ts_code.tolist()

try:
    m_tmp = ak.stock_market_fund_flow().rename(columns={'日期':'date',
                    '上证-收盘价':'sh_colse',
                    '上证-涨跌幅':'sh_pct',
                    '深证-收盘价':'sz_colse',
                    '深证-涨跌幅':'sz_pct',
                    '主力净流入-净额':'main_net',
                    '主力净流入-净占比':'main_net_pct',
                    '超大单净流入-净额':'super_net',
                    '超大单净流入-净占比':'super_net_pct',
                    '大单净流入-净额':'latge_net',
                    '大单净流入-净占比':'large_net_pct',
                    '中单净流入-净额':'mid_net',
                    '中单净流入-净占比':'mid_net_pct',
                    '小单净流入-净额':'small_net',
                    '小单净流入-净占比':'small_net_pct'})
    m_tmp.to_sql('mkFund', engDF, if_exists='replace', index=False)
except:
    pass
ls = []
for ID in tqdm(StockLists):
    try:
        df_tmp = ak.stock_individual_fund_flow(stock=ID[:6], market=ID[7:].lower()).rename(columns={'日期':'date',
                    '收盘价':'colse',
                    '涨跌幅':'pct',
                    '主力净流入-净额':'main_net',
                    '主力净流入-净占比':'main_net_pct',
                    '超大单净流入-净额':'super_net',
                    '超大单净流入-净占比':'super_net_pct',
                    '大单净流入-净额':'latge_net',
                    '大单净流入-净占比':'large_net_pct',
                    '中单净流入-净额':'mid_net',
                    '中单净流入-净占比':'mid_net_pct',
                    '小单净流入-净额':'small_net',
                    '小单净流入-净占比':'small_net_pct'})
        df_tmp.to_sql(ID[:6], engDF, if_exists='replace',index=False)
        time.sleep(random.randint(0,1))
    except:
        ls.append(ID)
        continue


print(ls)
engDF.dispose()
engS.dispose()