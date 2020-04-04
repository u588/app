import pandas as pd
import datetime

"""
    所选指数成分股组合在选定时期的数据集
   
"""
days =['2001-06-14', '2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', ]

# Day = '2018-01-29'
IndexOne = pd.read_csv('f:/indexone.csv')

# for i, Day in enumerate(days):
#     Day = datetime.datetime.strptime(Day, '%Y-%m-%d')
#     n = 21
#     IDay1 = Day + datetime.timedelta(days= -n)
#     IDay2 = Day + datetime.timedelta(days=n)
#     Day = Day.strftime('%Y-%m-%d')
#     IDay1 = IDay1.strftime('%Y-%m-%d')
#     IDay2 = IDay2.strftime('%Y-%m-%d')

#     ii = IndexOne[(IndexOne['date']>IDay1) & (IndexOne['date']<=IDay2)]
#     ii.set_index('date', inplace=True)
#     ii.to_csv('f:/IndexsSet/I' + Day + 'PonitSplit.csv')
#     print(Day, 'PonitSplit.csv saved ! ')

# Index = '399809'
# IDay1 = '2018-09-12'
# IDay2 = '2018-02-01'
# SDay1 = '20180912'
# SDay2 = '20180201'



i1 = IndexOne[IndexOne['datetime']<='2001-06-14']
i1.set_index('datetime', inplace=True)
i1.to_csv('f:/IndexsSet/I1996-12-17Split.csv')

i2 = IndexOne[(IndexOne['datetime']>'2001-06-14') & (IndexOne['datetime']<='2005-06-06')]
i2.set_index('datetime', inplace=True)
i2.to_csv('f:/IndexsSet/I2001-06-14Split.csv')

i3 = IndexOne[(IndexOne['datetime']>'2005-06-06') & (IndexOne['datetime']<='2007-10-16')]
i3.set_index('datetime', inplace=True)
i3.to_csv('f:/IndexsSet/I2005-06-06Split.csv')

i4 = IndexOne[(IndexOne['datetime']>'2007-10-16') & (IndexOne['datetime']<='2008-10-28')]
i4.set_index('datetime', inplace=True)
i4.to_csv('f:/IndexsSet/I2007-10-16Split.csv')

i5 = IndexOne[(IndexOne['datetime']>'2008-10-28') & (IndexOne['datetime']<='2009-08-04')]
i5.set_index('datetime', inplace=True)
i5.to_csv('f:/IndexsSet/I2008-10-28Split.csv')

i6 = IndexOne[(IndexOne['datetime']>'2009-08-04') & (IndexOne['datetime']<='2013-06-25')]
i6.set_index('datetime', inplace=True)
i6.to_csv('f:/IndexsSet/I2009-08-04Split.csv')

i7 = IndexOne[(IndexOne['datetime']>'2013-06-25') & (IndexOne['datetime']<='2015-06-12')]
i7.set_index('datetime', inplace=True)
i7.to_csv('f:/IndexsSet/I2013-06-25Split.csv')

i8 = IndexOne[(IndexOne['datetime']>'2015-06-12') & (IndexOne['datetime']<='2016-01-27')]
i8.set_index('datetime', inplace=True)
i8.to_csv('f:/IndexsSet/I2015-06-12Split.csv')

i9 = IndexOne[(IndexOne['datetime']>'2016-01-27') & (IndexOne['datetime']<='2018-01-29')]
i9.set_index('datetime', inplace=True)
i9.to_csv('f:/IndexsSet/I2016-01-27Split.csv')

i10 = IndexOne[(IndexOne['datetime']>'2018-01-29')] # & (IndexOne['datetime']<='2018-09-18')
i10.set_index('datetime', inplace=True)
i10.to_csv('f:/IndexsSet/I2018-01-29Split.csv')
print('f:/IndexsSet/I2018-01-29Split.csv saved !')

# i11 = IndexOne[(IndexOne['datetime']>'2018-09-18')]
# i11.set_index('datetime', inplace=True)
# i11.to_csv('f:/IndexsSet/I2018-09-18Split.csv')






# i0 = IndexOne[(IndexOne['date']>=IDay1)]# & (IndexOne['date']<=IDay2)]
# i0.set_index('date', inplace=True)
# i0.to_csv('f:/IndexsSet/I' + IDay1 +'Split.csv')
# i0.reset_index(inplace=True)
# i0 = i0[['date', Index]]
# ii = i0.drop('date', axis=1)


# StockOne = pd.read_csv('f:/StocksSet/I' + Index + 'Const.csv', dtype={'timestamp':object})

# s1 = StockOne[StockOne['timestamp']<='20010614']
# s2 = StockOne[(StockOne['timestamp']>'20010614') & (StockOne['timestamp']<='20050606')]
# s3 = StockOne[(StockOne['timestamp']>'20050606') & (StockOne['timestamp']<='20071016')]
# s4 = StockOne[(StockOne['timestamp']>'20071016') & (StockOne['timestamp']<='20081028')]
# s5 = StockOne[(StockOne['timestamp']>'20081028') & (StockOne['timestamp']<='20090804')]
# s6 = StockOne[(StockOne['timestamp']>'20090804') & (StockOne['timestamp']<='20130625')]
# s7 = StockOne[(StockOne['timestamp']>'20130625') & (StockOne['timestamp']<='20150612')]
# s8 = StockOne[(StockOne['timestamp']>'20150612') & (StockOne['timestamp']<='20160127')]
# s9 = StockOne[(StockOne['timestamp']>'20160127') & (StockOne['timestamp']<='20180129')]
# s10 = StockOne[(StockOne['timestamp']>'20180129')]
# s0 = StockOne[(StockOne['timestamp']>=SDay1)]# & (StockOne['timestamp']<=SDay2)]
# s0.set_index('timestamp',inplace=True)
# s0.to_csv('f:/StocksSet/I' + Index +'Split.csv')
# s0.reset_index(inplace=True)

# IndexCodess = s0.drop('timestamp', axis=1).head(0).T.copy()
# IndexCodess['Corr'] = 0.
# IndexCodes = IndexCodess.index.tolist()


# for i, IndexCo in enumerate(IndexCodes):
#     print ('ICode', i, '/', len(IndexCodes))
#     print(IndexCo)
               
#     try:
#         IndexCodess['Corr'][i] = ii.corrwith(s0[IndexCo])[0]
#         print(IndexCodess['Corr'][i])
#     except:
#         pass
                    
# IndexCodess.to_csv('f:/指数成分股相关性/Ind' + Index + '.csv')