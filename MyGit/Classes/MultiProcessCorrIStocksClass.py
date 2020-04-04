from sqlalchemy import create_engine
import concurrent.futures
import multiprocessing
import pandas as pd

home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/Stocks')


def GetCorr(IndexOne,IndexCodess,IndexCodes):
    for i, IndexCode in enumerate(IndexCodes):
        print ('IndexCode', i, '/', len(IndexCodes))
        try:
            IndexCodess[IndexCode] = 0
            for i, IndexCo in enumerate(IndexCodes):
                print ('ICode', i, '/', len(IndexCodes))
                
                try:
    #              print(IndexOne[IndexCode[2:]])
                    IndexCodess.loc[i,[IndexCode]] = IndexOne[IndexCode].corr(IndexOne[IndexCo])
                    print(IndexCodess[IndexCode][i])
                except:
                    pass
                # if i>10:
                #     break
        except:
            pass
        # if i>2:
        #    break
    IndexCodess.to_csv('f:/s/Co' + IndexOne.head(1).timestamp.tolist()[0] + '.csv')


IndexOne = pd.read_sql('s2', eng)
s1 = IndexOne[IndexOne['timestamp']<='20010614']
s2 = IndexOne[(IndexOne['timestamp']>'20010614') & (IndexOne['timestamp']<='20050606')]
s3 = IndexOne[(IndexOne['timestamp']>'20050606') & (IndexOne['timestamp']<='20071016')]
s4 = IndexOne[(IndexOne['timestamp']>'20071016') & (IndexOne['timestamp']<='20081028')]
s5 = IndexOne[(IndexOne['timestamp']>'20081028') & (IndexOne['timestamp']<='20090804')]
s6 = IndexOne[(IndexOne['timestamp']>'20090804') & (IndexOne['timestamp']<='20130625')]
s7 = IndexOne[(IndexOne['timestamp']>'20130625') & (IndexOne['timestamp']<='20150612')]
s8 = IndexOne[(IndexOne['timestamp']>'20150612') & (IndexOne['timestamp']<='20160127')]
s9 = IndexOne[(IndexOne['timestamp']>'20160127') & (IndexOne['timestamp']<='20180129')]
s10 = IndexOne[(IndexOne['timestamp']>'20180129')]

IndexO = [s1, s2, s3, s4, s5, s6, s7, s8 ,s9 ,s10]

IndexCodess = pd.read_sql('StocksList', eng)[['ts_code', 'symbol', 'name']][800:1600]
IndexCodes = IndexCodess.symbol.tolist()


def MultiCorr(workers, jobs, IndexCodess, IndexCodes):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(GetCorr, task, IndexCodess, IndexCodes)



if __name__ == '__main__':
    # for i in range(3):
    #     j = i*4
    MultiCorr(4,IndexO,IndexCodess, IndexCodes)

    
