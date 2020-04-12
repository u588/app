from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MarkCap')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

dateToday = datetime.datetime.today().strftime('%Y%m%d')

try:
	margin = pro.margin(trade_date=tradeDate)
	margin.set_index(['trade_date'], inplace=True)
	pd.io.sql.to_sql(margin, 'Margin', eng, if_exists='append')
#		print ('intraday for all stocks got.')
except:
	pass
#	if i>1:
#	   break 

print ('融资融券交易汇总 ok')