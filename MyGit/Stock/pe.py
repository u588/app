import pandas  as pd
import datetime
import tushare as ts
import time
from sqlalchemy import create_engine

days =['2001-06-14','2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']

ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')
pro = ts.pro_api()
pro.daily_basic(ts_code='', trade_date='20180726', start_date='', end_date='')

Day = '20150612'
home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/DailyBas')
engD = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/DailyBasD')

Bas = pro.daily_basic(trade_date=Day)