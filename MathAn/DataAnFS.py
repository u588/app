import pandas as pd
import datetime
import concurrent.futures
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engFS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxFS')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

StocksList = pd.read_sql('StocksList', eng).code
eng.dispose()
n = int(len(StocksList)/5)
d1 = StocksList[:n]
d2 = StocksList[n:2*n]
d3 = StocksList[2*n:3*n]
d4 = StocksList[3*n:4*n]
d5 = StocksList[4*n:]

ss = pd.DataFrame(columns=['code'], dtype=object)

def getlist(lis):
    sl = pd.DataFrame(columns=['code'], dtype=object)
    for i, j in enumerate(lis):
        try:
            df = pd.read_sql(j, engFS)
            dd = df['col1']-df['col1'].shift(1)
            if (dd.tail(2) > 0).all():
                sl.loc[i,'code'] = j
            else:
                # print(j)
                pass
        except:
            pass
    engFS.dispose()
    return sl

def Merg(res):
    global ss
    a = res.result()
    ss = pd.concat([ss, a])
    return ss

data1 = [d1,d2,d3,d4,d5]

def MultiGet(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(getlist, task).add_done_callback(Merg)
    pool.shutdown()


if __name__ == '__main__':
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    MultiGet(5,data1)


    ss.reset_index(drop=True,inplace=True)
    ss.to_sql('StockFS', engAn, if_exists='replace')

    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('ss: ' + str(len(ss)))
   