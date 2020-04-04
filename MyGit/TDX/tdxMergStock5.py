from sqlalchemy import create_engine
import pandas as pd
import tushare as ts

"""
    融合所有指数的每日收盘价为一个数据表
"""
home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks5')


StockLists = ts.get_stock_basics().sort_index().index.tolist()

d = pd.read_sql('000001', eng)[['datetime', 'close']]

for i, StockCode in enumerate(StockLists):
    try:
        print ('Index', i, '/', len(StockLists))
        a = pd.read_sql(StockCode, eng)[['datetime', 'close']]
        a.close = a.close.astype('float32').round(2)
        a.columns = ['datetime', StockCode]
        d = d.set_index('datetime').join(a.set_index('datetime'))
        d.reset_index(inplace=True)
        print(StockCode, '融入数据集')
    except:
        pass

    # if i>1:
    #    break

d.drop('close', axis=1,inplace=True)
d.set_index('datetime', inplace=True)
d.fillna(method='ffill', inplace=True)
d.to_csv('e:\StocksOne5.csv', encoding='utf8')
#d.to_sql('StocksOne', eng, if_exists='replace')
print('数据集融合完成')