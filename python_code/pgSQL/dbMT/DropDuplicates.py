import pandas as pd
from sqlalchemy import create_engine


job = '1.1.1.5:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks5')
engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
StockLists =  pd.read_sql('StocksList', engS).code.tolist()

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

