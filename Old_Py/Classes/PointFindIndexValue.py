import pandas as pd


days =['2001-06-14', '2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']

Day = '2018-02-12'

IndexLists = pd.read_csv('f:/indexlist.csv', dtype={'index_code':object})

def Value(day, IndexData, df):
    IndexData.reset_index(inplace=True)
    ColumnsLists = ['75%', '50%', '25%', 'mean', 'std', 'min']
    MergB = pd.DataFrame(columns=['index_code','count'])
    MergS = pd.DataFrame(columns=['index_code','count'])
    #数据清洗，丢掉空值行
    IndexData.dropna(thresh=4, inplace=True)
    for i, ColumnsList in enumerate(ColumnsLists):
        print ('ColumnsList',ColumnsList, i, '/', len(ColumnsLists))

       #'max'的前10个
        B = IndexData.sort_values(ColumnsList, ascending=False).head(15)[['index_code', 'count']]
        MergB = pd.concat([MergB,B], ignore_index=True)    
        S = IndexData.sort_values(ColumnsList).head(15)[['index_code', 'count']]
        MergS = pd.concat([MergS,S], ignore_index=True)
    
    MergB.drop('count', axis=1, inplace=True)
    MergB.drop_duplicates(subset='index_code', inplace=True)

    MergS.drop('count', axis=1, inplace=True)
    MergS.drop_duplicates(subset='index_code', inplace=True)

      #控制入选成分股
    # df = pd.read_excel('f:/plotindexlists.xls',dtype={'index_code':object})
    MergB = pd.merge(MergB, df, on='index_code')
    MergB.set_index('index_code', inplace=True)
    MergB.to_csv('f:/IndexsSet/I' + day +'PointUp.csv', encoding='utf-8')
    print('MergB saved.')

    MergS = pd.merge(MergS, df, on='index_code')
    MergS.set_index('index_code', inplace=True)
    MergS.to_csv('f:/IndexsSet/I' + day +'PointDown.csv', encoding='utf-8')
    print('MergS saved.')
    return MergB,MergS



# Value(IndexLists, Day)