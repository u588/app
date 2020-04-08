from sqlalchemy import create_engine
import pandas as pd

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

engdb = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/db')

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/Stocks')


# def GetStock(Stock,d):
#     print(d.head())
#     a = pd.read_sql(Stock, engdb)[['timestamp', 'close']]
#     a.columns = ['timestamp', Stock]
#     d = d.set_index('timestamp').join(a.set_index('timestamp'))
#     d.reset_index(inplace=True)
   

#    pd.io.sql.to_sql(ciIndex, cIndex, eng, if_exists='append')



StocksList = pd.read_sql('StocksList', eng)
Stocks = StocksList.ts_code.tolist()
d = pd.read_sql('000001.SZ',engdb)[['timestamp', 'close']]

for i, Stock in enumerate(Stocks):
    try:
        print ('Index', i, '/', len(Stocks))
        a = pd.read_sql(Stock, engdb)[['timestamp', 'close']]
        a.columns = ['timestamp', Stock]
        d = d.set_index('timestamp').join(a.set_index('timestamp'))
        d.reset_index(inplace=True)
    except:
        pass

    # if i>1:
    #    break

d.drop('close', axis=1,inplace=True)


d.to_csv('f:/Stocks.csv')