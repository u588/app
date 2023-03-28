from sqlalchemy import create_engine
import pandas as pd

engS = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxStocks5')
eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxStocks')

stocks = pd.read_sql('StocksList', eng).ts_code.tolist()

for i, stock in enumerate(stocks):
    try:
        print('Stock', i, '/', len(stocks))
        stock = stock[:6]
        sql ='DELETE FROM "'+stock+'" WHERE datetime= \'2021-07-16 15:00\' ;'
        result = eng.execute(sql)
        print(stock, 'droped !')
    except:
        pass
#    if i>2:
#        break 
