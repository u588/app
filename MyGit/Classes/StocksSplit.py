import pandas as pd
import datetime

"""
    所选成分股组合在选定时期的数据集
   
"""
days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', '2018-09-18']

#days = ['2018-09-18']

file = 'Down'
#file = 'Down'

#Day = '2018-09-18'
def StocksSplit(Day, file):
    StockOne = pd.read_csv('f:/StocksSet/S' + Day + file + 'Constdb.csv', dtype={'timestamp':object})
    StockOne.dropna(how='all', axis=1, inplace=True)   
    Day = datetime.datetime.strptime(Day, '%Y-%m-%d')
    n = 21
    SDay1 = Day + datetime.timedelta(days= -n)
    SDay2 = Day + datetime.timedelta(days=n)
    Day = Day.strftime('%Y%m%d')
    SDay1 = SDay1.strftime('%Y%m%d')
    SDay2 = SDay2.strftime('%Y%m%d')

    ss = StockOne[(StockOne['timestamp']>SDay1) & (StockOne['timestamp']<=SDay2)]
    ss.set_index('timestamp', inplace=True)
    ss.to_csv('f:/StocksSet/S' + Day + file + 'PointSplit.csv')
    print(Day, 'Splited !')

# IDay2 = '2018-02-01'
# SDay1 = '20180912'
# SDay2 = '20180201'

def Split(Day, file):
    StockOne = pd.read_csv('f:/StocksSet/S' + Day + file + 'Constdb.csv', dtype={'timestamp':object})
    StockOne.dropna(how='all', axis=1, inplace=True) 
    s1 = StockOne[StockOne['timestamp']<='20010614']
    s2 = StockOne[(StockOne['timestamp']>'20010614') & (StockOne['timestamp']<='20050606')]
    s3 = StockOne[(StockOne['timestamp']>'20050606') & (StockOne['timestamp']<='20071016')]
    s4 = StockOne[(StockOne['timestamp']>'20071016') & (StockOne['timestamp']<='20081028')]
    s5 = StockOne[(StockOne['timestamp']>'20081028') & (StockOne['timestamp']<='20090804')]
    s6 = StockOne[(StockOne['timestamp']>'20090804') & (StockOne['timestamp']<='20130625')]
    s7 = StockOne[(StockOne['timestamp']>'20130625') & (StockOne['timestamp']<='20150612')]
    s8 = StockOne[(StockOne['timestamp']>'20150612') & (StockOne['timestamp']<='20160127')]
    s9 = StockOne[(StockOne['timestamp']>'20160127') & (StockOne['timestamp']<='20180129')]
    s10 = StockOne[(StockOne['timestamp']>'20180129')]
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
    # elif Day ==  '2018-09-18':
    #     ss = s5
    else:
       pass
    ss.set_index('timestamp', inplace=True)
    ss.to_csv('f:/StocksSet/S' + Day + file + 'Split.csv')
    print(Day, 'Splited !')
   
       
for i, day in enumerate(days):
    try:
        Split(day, file)
    except:
        pass
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