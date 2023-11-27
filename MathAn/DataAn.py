import pandas as pd
import concurrent.futures
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engFS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxFS')

StocksList = pd.read_sql('StocksList', eng).code
n = int(len(StocksList)/5)
d1 = StocksList[:n]
d2 = StocksList[n:2*n]
d3 = StocksList[2*n:3*n]
d4 = StocksList[3*n:4*n]
d5 = StocksList[4*n:]

# d1 = StocksList[:10]
# d2 = StocksList[20:30]
# d3 = StocksList[100:120]
# d4 = StocksList[300:320]
# d5 = StocksList[1000:1020]



ss = pd.DataFrame(columns=['code'], dtype=object)
sss = pd.DataFrame(columns=['code'], dtype=object)

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
    return sl

def getlistS(lis):
    sl = pd.DataFrame(columns=['code'], dtype=object)
    for i, j in enumerate(lis):
        try:
            df = pd.read_sql(j, eng)
            if (df.close.tail(20).tail(1).to_list()[0]-df.close.tail(20).head(1).to_list()[0]) > 0:
                sl.loc[i,'code'] = j
            else:
                # print(j)
                pass
        except:
            pass
    return sl

def Merg(res):
    global ss
    a = res.result()
    ss = pd.concat([ss, a])
    return ss

def MergS(res):
    global sss
    a = res.result()
    sss = pd.concat([sss, a])
    return sss

data1 = [d1,d2,d3,d4,d5]

def MultiGet(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(getlist, task).add_done_callback(Merg)

def MultiGetS(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(getlistS, task).add_done_callback(MergS)


if __name__ == '__main__':

    MultiGet(5,data1)
    ss.reset_index(drop=True, inplace=True)
    m = int(len(ss)/5)
    dd1 = StocksList[:m]
    dd2 = StocksList[m:2*m]
    dd3 = StocksList[2*m:3*m]
    dd4 = StocksList[3*m:4*m]
    dd5 = StocksList[4*m:]
    data2 = [dd1,dd2,dd3,dd4,dd5]

    MultiGetS(5,data2)



    print(len(sss)/len(ss))

    