import pandas as pd


days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']

# IndexLists = pd.read_csv('f:/indexlist.csv', dtype={'index_code':object})[['index_code', 'name', 'const', 'hot', 'cate']]

#Consts = '20180918Const'
# file = 'Up'
# file = 'Down'
files = ['Up', 'Down']

def GetStock(Consts, file):
    ConstsData = pd.read_csv('f:/StocksSet/S' + Consts + file + 'Descri.csv', dtype={'code':object})
    #去除全0的行
    ConstsData.mask(ConstsData==0, inplace=True)
    ConstsData.dropna(thresh=4, axis=0, inplace=True)
    ColumnsLists = ['75%', '50%', '25%', 'mean', 'max', 'min', 'std']
    MergB = pd.DataFrame(columns=['code','count'])
    MergS = pd.DataFrame(columns=['code','count'])
    #数据清洗，丢掉空值行
    for i, ColumnsList in enumerate(ColumnsLists):
        print ('ColumnsList',ColumnsList, i, '/', len(ColumnsLists))

    #'max'的前6个
        B = ConstsData.sort_values(ColumnsList, ascending=False).head(6)[['code', 'count']]
        MergB = pd.concat([MergB,B], ignore_index=True)    
        S = ConstsData.sort_values(ColumnsList).head(6)[['code', 'count']]
        MergS = pd.concat([MergS,S], ignore_index=True)

    MergB.drop('count', axis=1, inplace=True)
    MergB.drop_duplicates(subset='code', inplace=True)

    MergS.drop('count', axis=1, inplace=True)
    MergS.drop_duplicates(subset='code', inplace=True)


    df = pd.read_csv('f:/indexconst.csv',dtype={'code':object})[['code', 'name']]
    df.drop_duplicates(subset='code', inplace=True)
    MergB = pd.merge(MergB, df, on='code')
    MergB.set_index('code', inplace=True)
    MergB.to_csv('f:/StocksSet/S' + Consts + file +'Up.csv', encoding='utf-8')
    print('MergB saved.')

    MergS = pd.merge(MergS, df, on='code')
    MergS.set_index('code', inplace=True)
    MergS.to_csv('f:/StocksSet/S' + Consts + file + 'Down.csv', encoding='utf-8')

print('MergS saved.')


for i, file in enumerate(files):
    for i, day in enumerate(days):
    #   day = day[:4]+day[5:7]+day[8:]
        try:
            GetStock(day, file)
        except:
            pass
print('Consts NormDescri finshed !')
