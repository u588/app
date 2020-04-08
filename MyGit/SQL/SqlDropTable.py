from sqlalchemy import create_engine
import pandas as pd

engS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks5')
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

stocks = pd.read_sql('StockLists', eng).ts_code.tolist()

for i, stock in enumerate(stocks):
    try:
        print('Stock', i, '/', len(stocks))
        stock = stock[:6]
        sql ='DELETE FROM "'+stock+'" WHERE datetime= \'2019-09-04 15:00\' ;'
        result = eng.execute(sql)
        print(stock, 'droped !')
    except:
        pass
    if i>2:
        break 
