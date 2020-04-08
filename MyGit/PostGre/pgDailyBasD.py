from sqlalchemy import create_engine
import tushare as ts
import pandas  as pd
import datetime
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DailyBasD')
ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DailyBas')

pro = ts.pro_api()

def AppendStocks(Bas,Stock,i,Today):
    try:
        Day = pd.read_sql(Stock[:6], engB).tail(1)['datetime'].tolist()[0]
        if Day < Today:
            intraday = Bas.loc[i:i]
            intraday.set_index(['datetime'], inplace=True)
            pd.io.sql.to_sql(intraday, Stock[:6], engB, if_exists='append')
            print(Stock, 'saved !')
        else:
            pass
    except:
        intraday = Bas.loc[i:i]
        intraday.set_index(['datetime'], inplace=True)
        pd.io.sql.to_sql(intraday, Stock[:6], engB, if_exists='append')
        print(Stock, 'saved !')



dateToday = datetime.datetime.today().strftime('%Y%m%d')
Today = datetime.datetime.today().strftime('%Y-%m-%d')
Bas = pro.daily_basic(trade_date=dateToday)
Bas.set_index(['trade_date'], inplace=True)
Bas.index.name = 'datetime'
Bas.sort_index(inplace=True)
Bas.sort_values('ts_code', inplace=True)
Bas.index = pd.DatetimeIndex(Bas.index)
Bas.index = Bas.index.astype(str)
pd.io.sql.to_sql(Bas, dateToday, eng, if_exists='replace')

Bas.reset_index(inplace=True)
Stocks = Bas.ts_code.tolist()
for i, Stock in enumerate(Stocks):
    AppendStocks(Bas,Stock,i,Today)


print ('daily_basic for all stocks got.')
