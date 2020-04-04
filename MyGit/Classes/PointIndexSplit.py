import pandas as pd
import datetime

"""
    所选指数成分股组合在选定时期的数据集
   
"""
days =['2001-06-14', '2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', ]

Day = '2018-02-12'


def IndexSplit(Day, n, IndexOne):
    # IndexOne = pd.read_csv('f:/indexone.csv')
    # Day = datetime.datetime.strptime(Day, '%Y-%m-%d')
    #n = 30
    Day = datetime.datetime.strptime(Day, '%Y-%m-%d')
    # IDay1 = Day + datetime.timedelta(days= -n)
    IDay2 = Day + n
    Day = Day.strftime('%Y-%m-%d')
    # IDay1 = IDay1.strftime('%Y-%m-%d')
    IDay2 = IDay2.strftime('%Y-%m-%d')

    # ii = IndexOne[(IndexOne['date']>IDay1) & (IndexOne['date']<=IDay2)]
    ii = IndexOne[(IndexOne['datetime']>=Day) & (IndexOne['datetime']<=IDay2)]
    ii.datetime=ii.datetime.str.replace('15:00', '')
    ii.set_index('datetime', inplace=True)
    ii.index = pd.DatetimeIndex(ii.index)
    ii.to_csv('f:/IndexsSet/I' + Day + 'PointSplit.csv')
    print(Day, 'PointSplit.csv saved ! ')
    return ii

