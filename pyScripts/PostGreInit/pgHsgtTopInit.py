from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MarkCap')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

dateToday = datetime.datetime.today().strftime('%Y%m%d')
tradeDates = pd.date_range('20180102', dateToday).strftime('%Y%m%d').tolist()


for i, tradeDate in enumerate(tradeDates):
	try:
		print ('top10', i, '/', len(tradeDates))
		top10 = pro.hsgt_top10(trade_date=tradeDate)
		top10.set_index(['trade_date'], inplace=True)
		pd.io.sql.to_sql(top10, 'HsgtTop', eng, if_exists='append')
#		print ('intraday for all stocks got.')
		time.sleep(0.2)
	except:
		pass
#	if i>1:
#	   break 

print ('沪深股通十大成交股 ok')