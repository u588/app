import pandas as pd

"""
    以期初值为基点规格化数据， 寻找指数特点
    规格化后的文件存储于(F:\IndexsSet\) 文件夹
"""
def IndesNorm(IDay1):
    DataSet = pd.read_csv('f:/IndexsSet/I' + IDay1 +'Split.csv',dtype={'datetime':object})
    # 转换成日期型
    DataSet.fillna(method='bfill', inplace=True)
    DataSet.dropna(axis=1, inplace=True)
    DataSet.set_index('datetime', inplace=True)
    DataSet.index = pd.DatetimeIndex(DataSet.index)
    DataSet.dropna(how='all', axis=1, inplace=True)

    # Indexs['datetime'] = pd.to_datetime(Indexs['datetime'])
    # Indexs.set_index('datetime', inplace=True)

    DataNorm = DataSet.copy()
    #初始化
    DataLists = DataSet.columns.values.tolist()

    for i, Data in enumerate(DataLists):
        print('Data', i, '/', len(DataLists))
        # BasData = DataSet.loc[IDay1][i]
        for i in range(len(DataSet[Data])):
            #全区间用起始点为基线
            DataNorm[Data][i] = (((DataSet[Data][i] - DataSet[Data][0])/DataSet[Data][0])*100).round(3)
            # DataNorm[Data][i] = ((DataSet[Data][i] - BasData)/BasData)*100
            print(DataNorm[Data][i])    

 #    DataNorm.dropna(axis=1, inplace=True)
    DataNorm.to_csv('f:/IndexsSet/I' + IDay1 +'Norm.csv')
    T = DataNorm.describe().T
    T.dropna(thresh=4, inplace=True)
    T.reset_index(inplace=True)
    T.rename(columns={'index':'index_code'}, inplace=True)
    T.set_index('index_code', inplace=True)
    T.to_csv('f:/IndexsSet/I' + IDay1 +'Descri.csv')
