import pandas as pd
import StockNormDescri as StNor

days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']

Day = '2018-02-12'


def StockNorm(Day, F, DataSet):
    # DataSet = pd.read_csv('f:/StocksSet/S' + Day + file + 'PointSplit.csv', dtype={'datetime':object})
    DataSet.fillna(method='bfill', inplace=True)
    DataSet.dropna(axis=1, inplace=True)
    # DataSet.rename(columns={'datetime':'date'}, inplace=True)
    # 转换成日期型
    # DataSet.set_index('date', inplace=True)
    # DataSet.index = pd.DatetimeIndex(DataSet.index)

    # Indexs['date'] = pd.to_datetime(Indexs['date'])
    # Indexs.set_index('date', inplace=True)

    DataNorm = DataSet.copy()
    #初始化
    DataLists = DataSet.columns.values.tolist()

    for i, Data in enumerate(DataLists):
        print('Data', i, '/', len(DataLists))
        for i in range(len(DataSet[Data])):
            DataNorm[Data][i] = (((DataSet[Data][i] - DataSet[Data][0])/DataSet[Data][0])*100).round(3)
            print(DataNorm[Data][i])    
    #    DataNorm.dropna(axis=1, inplace=True)
    DataNorm.to_csv('f:/StocksSet/S' + Day + F + 'PointNorm.csv')

    T = DataNorm.describe().T
    T.dropna(thresh=4, inplace=True)
    T.reset_index(inplace=True)
    T.rename(columns={'index':'code'}, inplace=True)
    T.set_index('code', inplace=True)
    T.to_csv('f:/StocksSet/S' + Day + F + 'PointDescri.csv')
    return DataNorm,T

# for i, day in enumerate(days):
#      print ('Day', i, '/', len(days))
#      Inno.IndesNorm(day)
#      print(day, 'Index NormDescri finshed !')

# file = 'Down'
# file = 'Up'
# files = ['Up', 'Down']

# for i, file in enumerate(files):
#     StockNorm(Day, file)

# print('Consts NormDescri finshed !')