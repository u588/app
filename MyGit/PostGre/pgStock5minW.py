from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
import datetime, calendar
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/db')

def getStock(tiker):
    intraday = ts.get_hist_data(code=ticker,start=lastMon, end=dateToday, ktype='5')
    intraday.sort_index(inplace=True)
    intraday.index.name = 'timestamp'
    pd.io.sql.to_sql(intraday, ticker, eng, if_exists='append')



dateToday = datetime.datetime.today().strftime('%Y-%m-%d')

lastMon = datetime.date.today()
oneday = datetime.timedelta(days = 1)
while lastMon.weekday() != calendar.MONDAY:
    lastMon -= oneday
lastMon = lastMon.strftime('%Y-%m-%d')


tickersRawData = ts.get_stock_basics()
tickers = tickersRawData.index.tolist()

for i, ticker in enumerate(tickers):
    try:
        print ('intraday', i, '/', len(tickers))
        getStock(ticker)
        time.sleep(0.2)
    except:
        pass
    # if i>1:
    #   break 
#print ('intraday for all stocks got.')


