from sqlalchemy import create_engine
import pandas as pd

"""
    融合所有指数的每日收盘价为一个数据表
"""

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/csIndex')


IndexList = pd.read_sql('IndexList', eng)
IndexCodes = IndexList.code.tolist()
d = pd.read_sql('000001',eng)[['date', 'close']]

for i, IndexCode in enumerate(IndexCodes):
    try:
        IndexCode = IndexCode[2:]
        print ('Index', i, '/', len(IndexCodes))
        a = pd.read_sql(IndexCode, eng)[['date', 'close']]
        a.columns = ['date', IndexCode]
        d = d.set_index('date').join(a.set_index('date'))
        d.reset_index(inplace=True)
        print(IndexCode, '融入数据集')
    except:
        pass

    # if i>1:
    #    break

d.drop('close', axis=1,inplace=True)
d.set_index('date', inplace=True)
d.to_sql('IndexOne', eng, if_exists='replace')
print('数据集融合完成')