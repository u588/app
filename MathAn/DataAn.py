import pandas as pd
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engFS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxFS')

StocksList = pd.read_sql('StocksList', eng).code
n = int(len(StocksList)/5)
# d1 = StocksList[:n]
# d2 = StocksList[n:2*n]
# d3 = StocksList[2*n:3*n]
# d4 = StocksList[3*n:4*n]
# d5 = StocksList[4*n:]

d1 = StocksList[:10]
d2 = StocksList[20:30]
d3 = StocksList[100:120]
d4 = StocksList[300:320]
d5 = StocksList[1000:1020]



# sl = pd.DataFrame(columns=['code'], dtype=object)
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
    # print(sl)
    return sl

data = [d1,d2,d3,d4,d5]


import concurrent.futures
def MultiGet(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            fe = pool.submit(getlist, task).result()
            # print(fe)
            # return fe
    



if __name__ == '__main__':
    dfi = pd.DataFrame(columns=['code'], dtype=object)
    # result = []
    # result.append(MultiGet(5,data))

    # for result in result:
    #     print(result.get())


    dfi = pd.concat([dfi, MultiGet(5,data)])

    # for i in [0,1,2,3,4]:
    #    try:
    #        dfi = pd.concat([dfi, result[i]])
    #    except:
    #        pass
    print('ok')

    