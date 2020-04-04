from sqlalchemy import create_engine
import pandas as pd
"""
    所选指数成分股收盘价组成一个数据集
"""
home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = home

engdb = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/db')
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/Stocks')

#Stocks = ['601989.SH','600409.SH','601600.SH', '000839.SZ', '000792.SZ', '600256.SH','600312.SH','000400.SZ']
days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', '2018-09-18']

#day = '2005-06-06'
file = 'Up'
#file = 'Down'
# Index='399809'
def MakeDB(day, file):
    Stocks = pd.read_csv('f:/StocksSet/S' + day + file + 'Const.csv', dtype={'index_code':object, 'code':object})['code'].tolist()
    d = pd.read_sql('000001.SZ',engdb)[['timestamp', 'close']]

    for i, Stock in enumerate(Stocks):
        if Stock[0]=='6':
            Stock = Stock + '.SH'
        else:
            Stock = Stock + '.SZ'
        try:
            print ('Index', i, '/', len(Stocks))
            a = pd.read_sql(Stock, engdb)[['timestamp', 'close']]
            a.columns = ['timestamp', Stock[:6]]
            d = d.set_index('timestamp').join(a.set_index('timestamp'))
            d.reset_index(inplace=True)
            print('Stock', Stock, 'got!')
        except:
            pass

    d.drop('close', axis=1,inplace=True)
    d.set_index('timestamp', inplace=True)
    d.to_csv('f:/StocksSet/S' + day + file + 'Constdb.csv')
    print('数据集建立')

for i, day in enumerate(days):
    try:
        MakeDB(day,file)
    except:
        pass