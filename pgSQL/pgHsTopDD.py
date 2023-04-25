from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/MarkCap')


dateToday = datetime.datetime.today().strftime('%Y-%m-%d')


try:
	top10 = ts.top_list(dateToday)
	top10.set_index(['date'], inplace=True)
	pd.io.sql.to_sql(top10, 'HsTop', eng, if_exists='append')
except:
	pass
#	if i>1:
#	   break 



print (' == 沪深每日龙虎榜 ==')