from sqlalchemy import create_engine
import pandas as pd
import concurrent.futures
import multiprocessing as mp

"""
    融合所有指数的每日收盘价为一个数据表
"""
home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs5')


IndexList = pd.read_sql('IndexList', eng)
IndexCodes = IndexList.index_code.tolist()
d = pd.read_sql('000001', eng)[['datetime', 'close']]

def FindClose(IndexCode):
    try:
        a = pd.read_sql(IndexCode, eng)[['datetime', 'close']]
        a.close = a.close.astype('float32').round(2)
        a.columns = ['datetime', IndexCode]
        print(IndexCode, '融入数据集')
    except:
        pass
    return a

def Merg(res):
    global d
    a = res.result()
    d = d.set_index('datetime').join(a.set_index('datetime'))
    d.reset_index(inplace=True)
    return d

def MultiMergIndex(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for IndexCode in jobs:
            pool.submit(FindClose, IndexCode).add_done_callback(Merg)

if __name__ == '__main__':
    MultiMergIndex(6, IndexCodes)

    d.drop('close', axis=1,inplace=True)
    d.fillna(method='ffill', inplace=True)
    d.set_index('datetime', inplace=True)
    d.sort_index(axis=1, inplace=True)
    d.to_sql('IndexOne5', eng, if_exists='replace')
    d.to_csv('e:/IndexOne5.csv', encoding='utf8')
print('数据集融合完成')