from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MarkCap')


dateToday = datetime.datetime.today().strftime('%Y-%m-%d')

try:
	top10 = ts.inst_tops()
	top10['timestamp'] = dateToday
	top10.set_index(['timestamp'], inplace=True)
	pd.io.sql.to_sql(top10, 'Hs5DInstTop', eng, if_exists='append')
except:
	pass
#	if i>1:
#	   break 

print ('5日机构席位上榜统计 ok')