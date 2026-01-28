
from sqlalchemy import create_engine
import pandas as pd
import akshare as ak

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
    DayUp = m_tmp.tail(1)['date'].to_list()[0]
    Day = pd.read_sql('mkFund', engDF).tail(1)['date'].to_list()[0]
    if pd.to_datetime(DayUp) > pd.to_datetime(Day):
       m_tmp.tail(1).to_sql('mkFound', engDF, if_exists='append', index=False)
    else:
        pass   
except:
    pass

for ID in StockLists:
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
        DayUp = df_tmp.tail(1)['date'].to_list()[0]
        Day = pd.read_sql(ID[:6], engDF).tail(1)['date'].to_list()[0]
        if pd.to_datetime(DayUp) > pd.to_datetime(Day):
           df_tmp.tail(1).to_sql(ID[:6], engDF, if_exists='append',index=False)
           time.sleep(random.randint(0,1))
        else:
            pass
    except:
        continue
print('All saved !')
engDF.dispose()
engS.dispose()
