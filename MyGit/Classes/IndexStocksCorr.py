# from sqlalchemy import create_engine
# import concurrent.futures
# import multiprocessing
import pandas as pd

"""
    所选指数与股票组合在选定时期的相关性
"""

# eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/Stocks')
# engIn = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/csIndex')


Index = '399976'

IndexOne = pd.read_csv('f:/indexone.csv')[['date', Index]]
# i1 = IndexOne[IndexOne['date']<='2001-06-14']
# i2 = IndexOne[(IndexOne['date']>'2001-06-14') & (IndexOne['date']<='2005-06-06')]
# i3 = IndexOne[(IndexOne['date']>'2005-06-06') & (IndexOne['date']<='2007-10-16')]
# i4 = IndexOne[(IndexOne['date']>'2007-10-16') & (IndexOne['date']<='2008-10-28')]
# i5 = IndexOne[(IndexOne['date']>'2008-10-28') & (IndexOne['date']<='2009-08-04')]
# i6 = IndexOne[(IndexOne['date']>'2009-08-04') & (IndexOne['date']<='2013-06-25')]
# i7 = IndexOne[(IndexOne['date']>'2013-06-25') & (IndexOne['date']<='2015-06-12')]
# i8 = IndexOne[(IndexOne['date']>'2015-06-12') & (IndexOne['date']<='2016-01-27')]
# i9 = IndexOne[(IndexOne['date']>'2016-01-27') & (IndexOne['date']<='2018-01-29')]
# i10 = IndexOne[(IndexOne['date']>'2018-01-29')
i0 = IndexOne[(IndexOne['date']>'2018-01-01') & (IndexOne['date']<='2018-02-01')]
i0.set_index('date', inplace=True)
i0.reset_index(inplace=True)
ii = i0.drop('date', axis=1)


StockOne = pd.read_csv('f:/StocksSet/I' + Index + 'Const.csv', dtype={'timestamp':object})
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
s0 = StockOne[(StockOne['timestamp']>'20180101') & (StockOne['timestamp']<='20180201')]
s0.set_index('timestamp',inplace=True)
s0.reset_index(inplace=True)

IndexCodess = s0.drop('timestamp', axis=1).head(0).T.copy()
IndexCodess['Corr'] = 0.
IndexCodes = IndexCodess.index.tolist()


for i, IndexCo in enumerate(IndexCodes):
    print ('ICode', i, '/', len(IndexCodes))
    print(IndexCo)
               
    try:
        IndexCodess['Corr'][i] = ii.corrwith(s0[IndexCo])[0]
        print(IndexCodess['Corr'][i])
    except:
        pass
                    
IndexCodess.to_csv('f:/指数成分股相关性/Ind' + Index + '.csv')