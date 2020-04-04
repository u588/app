from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
#import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/MarkCap')


#dateToday = datetime.datetime.today().strftime('%Y%m%d')

try:
	top10 = ts.inst_detail()
	top10.sort_values('date', inplace=True)
#	top10.set_index(['date'], inplace=True)
#	top10.sort_index(inplace=True)
	history = pd.read_sql('HsInstDetail', eng)
	stamp = history.tail(1)['date'].tolist()[0]
	top10 = top10[(top10['date']>stamp)]
	top10.set_index(['date'], inplace=True)
	pd.io.sql.to_sql(top10, 'HsInstDetail', eng, if_exists='append')
except:
	pass

print ('机构成交明细 ok')