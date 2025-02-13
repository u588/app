import akshare as ak
import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56:5432/StockBas')

# 生成2010-2015年所有月份的序列 
ylist = [f"{year}{month:02d}" for year in range(2013, 2025) for month in range(1,13)] + ['202501']

ddf = []
for n in ylist:
    df = ak.stock_szse_sector_summary(symbol="当月", date= n ).drop('项目名称-英文',axis=1)
    df['日期'] = n
    ddf.append(df)

dff = pd.concat(ddf)
dff.set_index('日期').to_sql('szSum', eng, if_exists="replace")