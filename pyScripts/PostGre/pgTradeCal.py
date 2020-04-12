from sqlalchemy import create_engine
import tushare as ts
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MarkCap')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()
TradeCal = pro.trade_cal().tail(730)
TradeCal.set_index(['cal_date'], inplace=True)

pd.io.sql.to_sql(TradeCal, 'TradeCal', eng, if_exists='append')

print ('交易日历 ok')