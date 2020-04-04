from sqlalchemy import create_engine
import pandas as pd

"""
    融合所有指数的每日收盘价为一个数据表
"""
home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = home

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs')


IndexList = pd.read_sql('IndexList', eng)
IndexCodes = IndexList.index_code.tolist()
d = pd.read_sql('000001', eng)[['datetime', 'close']]

for i, IndexCode in enumerate(IndexCodes):
    try:
        print ('Index', i, '/', len(IndexCodes))
        a = pd.read_sql(IndexCode, eng)[['datetime', 'close']]
        a.close = a.close.astype('float32').round(2)
        a.columns = ['datetime', IndexCode]
        d = d.set_index('datetime').join(a.set_index('datetime'))
        d.reset_index(inplace=True)
        print(IndexCode, '融入数据集')
    except:
        pass

    # if i>1:
    #    break

d.drop('close', axis=1,inplace=True)
d.fillna(method='ffill', inplace=True)
d.set_index('datetime', inplace=True)
d.to_sql('IndexOne', eng, if_exists='replace')
print('数据集融合完成')