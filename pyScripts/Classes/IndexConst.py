# from sqlalchemy import create_engine
import pandas as pd

"""
    所选指数Index的成分股
"""

# eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/csIndex')
days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']




#day = '2005-06-06'
file = 'Up'
# file = 'Down'
def GetIndexConst(day, file):
    Indexs = pd.read_csv('f:/IndexsSet/I' + day + file + '.csv', dtype={'index_code':object})['index_code'].tolist()[:8]

    IndexConst = pd.read_csv('f:/IndexConst.csv', dtype={'index_code':object, 'code':object})

    #初始化成分股数据集
    Consts = pd.DataFrame(columns=['index_code', 'code', 'name'])
    for i, Index in enumerate(Indexs):
        print ('Index', Index, i, '/', len(Indexs))
        #建立成份股数据集
        Const = IndexConst[IndexConst.index_code==Index]
        #合并数据集
        Consts = pd.concat([Consts, Const], ignore_index=True)
    #成分股取重
    Consts.drop_duplicates(subset='code', inplace=True)
    Consts.set_index('index_code',inplace=True)
    Consts.to_csv('f:/StocksSet/S' + day + file + 'Const.csv', encoding='utf8')
    print('得到', day, '优选股')


for i, day in enumerate(days):
    try:
        GetIndexConst(day, file)
    except:
        pass