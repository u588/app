from sqlalchemy import create_engine
import tushare as ts
import pandas as pd

ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')


#股票基本信息
df = pro.stock_basic()
df.to_sql('StockBas',eng, if_exists='replace')
print('股票基本信息 ok')
