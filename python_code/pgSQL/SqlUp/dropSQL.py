import pandas as pd
from sqlalchemy import create_engine


job = '10.145.254.56'
ip = job


eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
StockLists =  pd.read_sql('StocksList', eng).code.tolist()


for i, StockCode in enumerate(StockLists):
    print('Index', i, '/', len(StockLists))
    if  StockCode >='002993' and StockCode<='605500':
        Data = pd.read_sql(StockCode, eng)
        Data = Data.drop(Data.tail(3).index)
        Data.set_index('datetime', inplace=True)
        Data.to_sql(StockCode, eng, if_exists='replace')
        print(StockCode + 'Drop !')
    else:
        pass
    
   