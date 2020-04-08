from sqlalchemy import create_engine
import data_fq  as fq
import pandas as pd

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
engX = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxXdXr')
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs')


StockLists = ['000001','002940']
# pd.read_sql('StockLists', engS).code.tolist()
d = pd.read_sql('000001', eng)[['datetime', 'close']]
d.datetime=d.datetime.str.replace('15:00', '')

for i, StockCode in enumerate(StockLists):
    print('Index', i, '/', len(StockLists))
    try:
        Data = pd.read_sql(StockCode, engS)
        # Data.to_csv('f:/'+StockCode+'.csv')
        XdXr = pd.read_sql(StockCode, engX)
        # XdXr.to_csv('f:/'+StockCode+'XdXr.csv')
        a = fq.qfq(Data, XdXr)
        a.reset_index('datetime', inplace=True)
        a = a[['datetime', 'close']]
        a.columns = ['datetime', StockCode]
        d = d.set_index('datetime').join(a.set_index('datetime'))
        d.reset_index(inplace=True)
        print(StockCode, '融入数据集')

        
    except:
        pass

d.drop('close', axis=1,inplace=True)
d.set_index('datetime', inplace=True)
d = d.fillna(method='ffill')
d.to_csv('e:\StocksOne.csv', encoding='utf8')
# d.to_sql('StocksOne', eng, if_exists='replace')
print('数据集融合完成')