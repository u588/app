import pandas as pd
"""
    所选指数成分股收盘价组成一个数据集
"""


days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', '2018-09-18']


# file = 'Up'
file = 'Down'

StocksData = pd.read_csv('f:/stocksone.csv')
# StocksData.rename(columns={'date':'datetime'}, inplace=True)
StockLists = pd.read_csv('f:/stocklists.csv', dtype={'code':object})

for i, Day in enumerate(days):
    print ('Stocks', i, '/', len(days))
    try:
        s = pd.read_csv('f:/StocksSet/S' + Day + file + 'Const.csv', dtype={'index_code':object, 'code':object})

        Stocks = s.merge(StockLists, on='code', how='inner').code.tolist()
        StockOne = StocksData[['datetime'] + Stocks]
        s1 = StockOne[StockOne['datetime']<='2001-06-14']
        s2 = StockOne[(StockOne['datetime']>'2001-06-14') & (StockOne['datetime']<='2005-06-06')]
        s3 = StockOne[(StockOne['datetime']>'2005-06-06') & (StockOne['datetime']<='2007-10-16')]
        s4 = StockOne[(StockOne['datetime']>'2007-10-16') & (StockOne['datetime']<='2008-10-28')]
        s5 = StockOne[(StockOne['datetime']>'2008-10-28') & (StockOne['datetime']<='2009-08-04')]
        s6 = StockOne[(StockOne['datetime']>'2009-08-04') & (StockOne['datetime']<='2013-06-25')]
        s7 = StockOne[(StockOne['datetime']>'2013-06-25') & (StockOne['datetime']<='2015-06-12')]
        s8 = StockOne[(StockOne['datetime']>'2015-06-12') & (StockOne['datetime']<='2016-01-27')]
        s9 = StockOne[(StockOne['datetime']>'2016-01-27') & (StockOne['datetime']<='2018-01-29')]
        s10 = StockOne[(StockOne['datetime']>'2018-01-29')]
        # s11 = StockOne[(StockOne['datetime']>'2018-09-18')]
        if Day == '2005-06-06':
            ss = s3
        elif Day == '2007-10-16':
            ss = s4
        elif Day ==  '2008-10-28':
            ss = s5
        elif Day ==  '2009-08-04':
            ss = s6
        elif Day ==  '2013-06-25':
            ss = s7
        elif Day ==  '2015-06-12':
            ss = s8
        elif Day ==  '2016-01-27':
            ss = s9
        elif Day ==  '2018-01-29':
            ss = s10
        elif Day ==  '2018-09-18':
            ss = s11
        else:
            pass
        ss.set_index('datetime', inplace=True)
        ss.to_csv('f:/StocksSet/S' + Day + file + 'Split.csv')
        print('f:/StocksSet/S' + Day + file + 'Split.csv', 'saved !')
    except:
        pass