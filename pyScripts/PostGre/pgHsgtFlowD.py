from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MarkCap')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')

pro = ts.pro_api()

tradeDate = datetime.datetime.today().strftime('%Y%m%d')

try:
	MoneyFlow = pro.moneyflow_hsgt(trade_date=tradeDate)
	MoneyFlow.set_index(['trade_date'], inplace=True)
	pd.io.sql.to_sql(MoneyFlow, 'HsgtFlow', eng, if_exists='append')
except:
	pass
#	if i>1:
#	break

#print ('沪深港通资金流向 ok')