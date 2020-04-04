from sqlalchemy import create_engine
import pandas as pd



eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/csIndex')



IndexList = pd.read_sql('IndexList', eng)
Stocks = IndexList.code.tolist()
d = pd.read_sql('000001',eng)[['date', 'close']]

for i, Stock in enumerate(Stocks):
    try:
        Stock = Stock[2:]
        print ('Index', i, '/', len(Stocks))
        a = pd.read_sql(Stock, eng)[['date', 'close']]
        a.columns = ['date', Stock]
        d = d.set_index('date').join(a.set_index('date'))
        d.reset_index(inplace=True)
    except:
        pass

    if i>1:
       break

d.drop('close', axis=1,inplace=True)
print(d.head())

