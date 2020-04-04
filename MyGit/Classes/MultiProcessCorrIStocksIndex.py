from sqlalchemy import create_engine
import concurrent.futures
import multiprocessing
import pandas as pd



# eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/Stocks')
Stocksdb = pd.read_csv('f:/stocks.csv', dtype={'timestamp':object})
Indexdb = pd.read_csv('f:/indexone.csv')



def GetCorr(StockOne,IndexCodess,IndexCodes,StockCodes):
    for i, StockCode in enumerate(StockCodes):
        print ('StockCode', i, '/', len(StockCodes))
        try:
            IndexCodess[StockCode] = 0
            for i, IndexCo in enumerate(IndexCodes):
                print ('ICode', i, '/', len(IndexCodes))
                
                try:
    #              print(IndexOne[IndexCode[2:]])
                    IndexCodess.loc[i,[StockCode]] = StockOne[StockCode].corr(StockOne[IndexCo])
                    print(IndexCodess[StockCode][i])
                except:
                    pass
                # if i>10:
                #     break
        except:
            pass
        # if i>2:
        #    break
    IndexCodess.to_csv('f:/股票指数分布/' + StockOne.head(1).index.tolist()[0].strftime('%Y-%m-%d') + '.csv')
#时间型索引转换成字符串

def MergeDf(ii, ss):
    ii['date'] = pd.to_datetime(ii['date'])
    ii.set_index('date', inplace=True)
    ss['timestamp'] = pd.to_datetime(ss['timestamp'])
    ss.set_index('timestamp', inplace=True)
    Df = pd.concat([ii, ss], axis=1, join='outer')
    return Df

IndexOne = Indexdb
i1 = IndexOne[IndexOne['date']<='2001-06-14']
i2 = IndexOne[(IndexOne['date']>'2001-06-14') & (IndexOne['date']<='2005-06-06')]
i3 = IndexOne[(IndexOne['date']>'2005-06-06') & (IndexOne['date']<='2007-10-16')]
i4 = IndexOne[(IndexOne['date']>'2007-10-16') & (IndexOne['date']<='2008-10-28')]
i5 = IndexOne[(IndexOne['date']>'2008-10-28') & (IndexOne['date']<='2009-08-04')]
i6 = IndexOne[(IndexOne['date']>'2009-08-04') & (IndexOne['date']<='2013-06-25')]
i7 = IndexOne[(IndexOne['date']>'2013-06-25') & (IndexOne['date']<='2015-06-12')]
i8 = IndexOne[(IndexOne['date']>'2015-06-12') & (IndexOne['date']<='2016-01-27')]
i9 = IndexOne[(IndexOne['date']>'2016-01-27') & (IndexOne['date']<='2018-01-29')]
i10 = IndexOne[(IndexOne['date']>'2018-01-29')]

IndexO = [i1, i2, i3, i4, i5, i6, i7, i8 ,i9 ,i10]


StockOne = Stocksdb
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

StocksO = [s1, s2, s3, s4, s5, s6, s7, s8 ,s9 ,s10]

jobs = [[i1,s1], [i2,s2], [i3,s3], [i4,s4], [i5,s5], [i6,s6], [i7,s7], [i8,s8], [i9,s9], [i10,s10]]



IndexCodess = pd.read_excel('f:/indexlist.xls', dtype={'index_code':object})[['index_code', 'name', 'const', 'hot']]
IndexCodes = IndexCodess.index_code.tolist()
StockCodes = Stocksdb.columns.tolist()[1:]



def MultiCorr(workers, jobs,IndexCodess,IndexCodes,StockCodes):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in jobs:
            try:
                Mjob = MergeDf(job[0], job[1])
                pool.submit(GetCorr, Mjob, IndexCodess, IndexCodes,StockCodes)
                    
            except:
                pass


if __name__ == '__main__':
    # for i in range(3):
    #     j = i*4
    MultiCorr(4,jobs,IndexCodess, IndexCodes, StockCodes)    
