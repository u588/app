from sqlalchemy import create_engine
import pandas as pd
# import datetime
# import time

engdb = create_engine(
    'postgresql+psycopg2://sa:11111111@10.145.254.55:5432/Fq')
engBas = create_engine(
    'postgresql+psycopg2://sa:11111111@10.145.254.55:5432/StockBas')

StocksRaw = pd.read_sql('StockBas', engBas)
Stocks = StocksRaw.symbol.tolist()


def StocksMA(Stock):
    Stock['MA_5'] = Stock.close.rolling(5).mean().round(2)
    Stock['MA_21'] = Stock.close.rolling(21).mean().round(2)
    Stock['MA_55'] = Stock.close.rolling(55).mean().round(2)


def StocksVol(Stock):
    Stock['Vol_5'] = Stock.volume.rolling(5).mean().round(2)
    Stock['Vol_21'] = Stock.volume.rolling(21).mean().round(2)
    Stock['Vol_55'] = Stock.volume.rolling(55).mean().round(2)


def StcokVol


for i, Stock in enumerate(Stocks):
    try:
        print('Stock', i, '/', len(Stocks))
        StockData = pd.read_sql(Stock, engdb)
        StockData['date'] = pd.to_datetime(StockData['date'])
        StockData.set_index('date', inplace=True)

        StocksMA(StockData)
        StocksVol(StockData)

        df = StockData

        df1 = df[(df['MA_55'] == df['MA_21']) & (df['MA_21'] < df['MA_5'])]

        df1 = df1[df1.index > '2018-07-01']

        if df1.empty:
            pass
        else:
            df1.to_csv('f:/qutdata/8/' + Stock + '.csv')
            print(Stock + ' got')

    except:
        pass
#    if i > 100:
#       break
