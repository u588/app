from sqlalchemy import create_engine
import concurrent.futures
import multiprocessing
import pandas as pd


home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/csIndex')


def GetCorr(IndexOne,IndexCodess,IndexCodes):
    for i, IndexCode in enumerate(IndexCodes):
        print ('IndexCode', i, '/', len(IndexCodes))
        try:
            IndexCodess[IndexCode] = 0
            for i, IndexCo in enumerate(IndexCodes):
                print ('ICode', i, '/', len(IndexCodes))
                
                try:
    #              print(IndexOne[IndexCode[2:]])
                    IndexCodess.loc[i,[IndexCode]] = IndexOne[IndexCode[2:]].corr(IndexOne[IndexCo[2:]])
                    print(IndexCodess[IndexCode][i])
                except:
                    pass
                # if i>10:
                #     break
        except:
            pass
        # if i>2:
        #    break
    IndexCodess.to_csv('f:/v/Corr' + IndexOne.head(1).date.tolist()[0] + '.csv')


IndexOne = pd.read_csv('f:/indexone.csv')
s1 = IndexOne[IndexOne['date']<='2001-06-14']
s2 = IndexOne[(IndexOne['date']>'2001-06-14') & (IndexOne['date']<='2005-06-06')]
s3 = IndexOne[(IndexOne['date']>'2005-06-06') & (IndexOne['date']<='2007-10-16')]
s4 = IndexOne[(IndexOne['date']>'2007-10-16') & (IndexOne['date']<='2008-10-28')]
s5 = IndexOne[(IndexOne['date']>'2008-10-28') & (IndexOne['date']<='2009-08-04')]
s6 = IndexOne[(IndexOne['date']>'2009-08-04') & (IndexOne['date']<='2013-06-25')]
s7 = IndexOne[(IndexOne['date']>'2013-06-25') & (IndexOne['date']<='2015-06-12')]
s8 = IndexOne[(IndexOne['date']>'2015-06-12') & (IndexOne['date']<='2016-01-27')]
s9 = IndexOne[(IndexOne['date']>'2016-01-27') & (IndexOne['date']<='2018-01-29')]
s10 = IndexOne[(IndexOne['date']>'2018-01-29')]

IndexO = [s1, s2, s3, s4, s5, s6, s7, s8 ,s9 ,s10]

IndexCodess = pd.read_sql('IndexList', eng)
IndexCodes = IndexCodess.code.tolist()




def MultiCorr(workers, jobs, IndexCodess, IndexCodes):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(GetCorr, task, IndexCodess, IndexCodes)



if __name__ == '__main__':
    # for i in range(3):
    #     j = i*4
    MultiCorr(4,IndexO,IndexCodess, IndexCodes)

    
