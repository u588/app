import pandas as pd
import datetime

"""
    所选指数成分股收盘价组成一个数据集
"""


days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', '2018-09-18']

Day = '2018-02-12'
file = 'Up'
# file = 'Down'

StocksData = pd.read_csv('f:/stocksone.csv')
# StocksData.rename(columns={'date':'datetime'}, inplace=True)
StockLists = pd.read_csv('f:/stocklists.csv', dtype={'code':object})

def MakeStockdb(Day, n, file, Const, StocksData, StockLists):
    # s = pd.read_csv('f:/StocksSet/S' + Day + 'Point' + file + 'Const.csv', dtype={'index_code':object, 'code':object})

    Stocks = Const.merge(StockLists, on='code', how='inner').code.tolist()
    StockOne = StocksData[['datetime'] + Stocks]



    Day = datetime.datetime.strptime(Day, '%Y-%m-%d')
    # n = 30
    # IDay1 = Day + datetime.timedelta(days= -n)
    IDay2 = Day + n
    Day = Day.strftime('%Y-%m-%d')
    # IDay1 = IDay1.strftime('%Y-%m-%d')
    IDay2 = IDay2.strftime('%Y-%m-%d')

    ss = StockOne[(StockOne['datetime']>=Day) & (StockOne['datetime']<=IDay2)]
    ss.set_index('datetime', inplace=True)
    ss.index = pd.DatetimeIndex(ss.index)
    ss.to_csv('f:/StocksSet/S' + Day + file + 'PointSplit.csv')
    print('f:/StocksSet/S' + Day + file + 'Split.csv', 'saved !')
    return ss
