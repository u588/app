from sqlalchemy import create_engine
import pandas as pd
import concurrent.futures
import multiprocessing as mp

"""
    融合所有指数的每日收盘价为一个数据表
"""
home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks5')
engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
engI = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs5')

StockLists = pd.read_sql('StockLists', engS).code.tolist()
s1 = StockLists[:1000]
s2 = StockLists[1001:2000]
s3 = StockLists[2001:3000]
s4 = StockLists[3001:]

def FindClose(StockCode):
    try:
        a = pd.read_sql(StockCode, eng)[['datetime', 'close']]
        a.close = a.close.astype('float32').round(2)
        a.columns = ['datetime', StockCode]
        print(StockCode, '取出数据')
    except:
        pass
    return a

def Merg(res):
    global d
    a = res.result()
    d = d.join(a.set_index('datetime'), on='datetime')
    print('数据集融合')
    # d.reset_index(inplace=True)
    return d

def MultiMergStock(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for StockCode in jobs:
            pool.submit(FindClose, StockCode).add_done_callback(Merg)

if __name__ == '__main__':

    d = pd.read_sql('000001', eng)[['datetime', 'close']]
    MultiMergStock(6, s1)
    d1=d.copy()
    d1.drop('close', axis=1,inplace=True)
    d1.drop_duplicates(subset='datetime', keep='first', inplace=True)

    d1.fillna(method='ffill', inplace=True)
    d1.to_csv('e:/d1.csv', encoding='utf8')
    print('d1 saved')

    d = pd.read_sql('000001', eng)[['datetime', 'close']]
    MultiMergStock(6, s2)
    d2 = d.copy()
    d2.drop('close', axis=1,inplace=True)
    d2.drop_duplicates(subset='datetime', keep='first', inplace=True)

    d2.fillna(method='ffill', inplace=True)
    d2.to_csv('e:/d2.csv', encoding='utf8')
    print('d2 saved')

    d = pd.read_sql('000001', eng)[['datetime', 'close']]
    MultiMergStock(6, s3)
    d3 = d.copy()
    d3.drop('close', axis=1,inplace=True)
    d3.drop_duplicates(subset='datetime', keep='first', inplace=True)

    d3.fillna(method='ffill', inplace=True)
    d3.to_csv('e:/d3.csv', encoding='utf8')
    print('d3 saved')

    d = pd.read_sql('000001', eng)[['datetime', 'close']]
    MultiMergStock(6, s4)
    d4=d.copy()
    d4.drop('close', axis=1,inplace=True)
    d4.drop_duplicates(subset='datetime', keep='first', inplace=True)
    d4.fillna(method='ffill', inplace=True)
    d4.to_csv('e:/d4.csv', encoding='utf8')
    print('d4 saved')

    dd = d1.join(d2.set_index('datetime'), on='datetime')
    dd = dd.join(d3.set_index('datetime'), on='datetime')
    dd = dd.join(d4.set_index('datetime'), on='datetime')
    
    dd.drop_duplicates(subset='datetime', keep='first', inplace=True)
    dd.set_index('datetime', inplace=True)
    dd.sort_index(axis=1, inplace=True)
    dd.to_csv('e:/StocksOne5.csv', encoding='utf8')
    print('数据集融合完成')