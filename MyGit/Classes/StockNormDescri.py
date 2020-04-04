import pandas as pd

"""
    以期初值为基点规格化数据， 寻找指数特点
    规格化的数据存储于(F:\StocksSet\) 文件夹
"""

def StockNorm(Index, file):
    DataSet = pd.read_csv('f:/StocksSet/S' + Index + file + 'Split.csv', dtype={'datetime':object})
    DataSet.fillna(method='bfill', inplace=True)
    DataSet.dropna(axis=1, inplace=True)
    DataSet.rename(columns={'datetime':'date'}, inplace=True)
    # 转换成日期型
    DataSet.set_index('date', inplace=True)
    DataSet.index = pd.DatetimeIndex(DataSet.index)

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
    DataNorm.to_csv('f:/StocksSet/S' + Index + file + 'Norm.csv')

    T = DataNorm.describe().T
    T.dropna(thresh=4, inplace=True)
    T.reset_index(inplace=True)
    T.rename(columns={'index':'code'}, inplace=True)
    T.set_index('code', inplace=True)
    T.to_csv('f:/StocksSet/S' + Index + file + 'Descri.csv')



# file = 'Down'
# day = '20180129'

# StockNorm(day, file)