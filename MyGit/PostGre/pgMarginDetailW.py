from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime, calendar
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/MarkCap')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

dateToday = datetime.datetime.today().strftime('%Y%m%d')

lastMon = datetime.date.today()
oneday = datetime.timedelta(days = 1)
while lastMon.weekday() != calendar.MONDAY:
    lastMon -= oneday
lastMon = lastMon.strftime('%Y%m%d')
tradeDates = pd.date_range(lastMon, periods=5).strftime('%Y%m%d').tolist()

for i, tradeDate in enumerate(tradeDates):
	try:
		margin = pro.margin_detail(trade_date=tradeDate)
		margin.set_index(['trade_date'], inplace=True)
		pd.io.sql.to_sql(margin, 'MargDetail', eng, if_exists='append')
		time.sleep(0.2)
	except:
		pass
#	if i > 1
#		break
print ('融资融券交易明细 ok')