import pandas as pd
import datetime
import concurrent.futures
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

sss = pd.DataFrame(columns=['code'], dtype=object)

    # print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
ls = pd.read_sql('StockFS', engAn).code
engAn.dispose()
m = int(len(ls)/5)
dd1 = ls[:m]
dd2 = ls[m:2*m]
dd3 = ls[2*m:3*m]
dd4 = ls[3*m:4*m]
dd5 = ls[4*m:]
data2 = [dd1,dd2,dd3,dd4,dd5]

def getlistS(lis):
    sl = pd.DataFrame(columns=['code'], dtype=object)
    for i, j in enumerate(lis):
        try:
            df = pd.read_sql(j, eng)
            if (df.close.tail(25).tail(1).to_list()[0]-df.close.tail(25).head(1).to_list()[0]) > 0:
                sl.loc[i,'code'] = j
            else:
                # print(j)
                pass
        except:
            pass
    eng.dispose()
    return sl

def MergS(res):
    global sss
    a = res.result()
    sss = pd.concat([sss, a])
    return sss

def MultiGetS(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(getlistS, task).add_done_callback(MergS)
    pool.shutdown()


if __name__ == '__main__':
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    MultiGetS(5,data2)

    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('sss: ' + str(len(sss)))
    print(len(sss)/len(ls))

