from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/StockFund')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

dateToday = datetime.datetime.today().strftime('%Y%m%d')
#tradeDates = pd.date_range('20170101', dateToday).strftime('%Y%m%d').tolist()

stocksRawData = pro.stock_basic()
stocks = stocksRawData['ts_code'].tolist()
history = pd.read_sql('TopHolders', eng)

for i, stock in enumerate(stocks):
	try:
#		print ('top10', i, '/', len(stocks))
		top10 = pro.top10_holders(ts_code=stock)
		top10.sort_values('end_date', inplace=True)
		top10['timestamp'] = dateToday
		top10.set_index(['timestamp'], inplace=True)
		stamp = history[history['ts_code'] == stock].tail(1)['end_date'].tolist()
		top10 = top10[(top10['end_date']>stamp)]
		pd.io.sql.to_sql(top10, 'TopHolders', eng, if_exists='append')
#		print ('top10_holders for ['+stock+'] got.')
		time.sleep(0.2)
	except:
		pass
#	if i>1:
#	   break 

print (' == 沪深前十大股东 ==')