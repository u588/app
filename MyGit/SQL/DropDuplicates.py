import pandas as pd
from sqlalchemy import create_engine

home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks5')
engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
StockLists =  pd.read_sql('StockLists', engS).code.tolist()

for i, StockCode in enumerate(StockLists):
    print('Index', i, '/', len(StockLists))
    # if StockCode >= '603885':
    df = pd.read_sql(StockCode, eng)
    df.drop_duplicates(subset='datetime', keep='first', inplace=True)

    df.set_index('datetime', inplace=True)
    df.to_sql(StockCode, eng, if_exists='replace')
    print(StockCode,'saved to sql !')

    # else:
    #     pass

