from sqlalchemy import create_engine
import tushare as ts
import pandas as pd
import datetime
import calendar
import time

engFq = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/Fq')
engBas = create_engine(
    'postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')


def FqStock(stock):
    intraday = ts.get_k_data(stock)
    intraday = intraday[intraday['date'] >= lastMon]
    intraday = intraday.set_index('date')
    pd.io.sql.to_sql(intraday, stock, engFq, if_exists='append')
#    print('FqStock for [' + stock + '] got.')


dateToday = datetime.datetime.today().strftime('%Y-%m-%d')
lastMon = datetime.date.today()
oneday = datetime.timedelta(days=1)
while lastMon.weekday() != calendar.MONDAY:
    lastMon -= oneday
lastMon = lastMon.strftime('%Y-%m-%d')

stocksRawData = pd.read_sql('StockBas', engBas)
stocks = stocksRawData.symbol.tolist()

for i, stock in enumerate(stocks):
    try:
#        print('FqStock', i, '/', len(stocks))
        FqStock(stock)
        time.sleep(0.2)
    except:
        pass
#    if i>1:
#      break
#print('FqStock for all stocks got.')
