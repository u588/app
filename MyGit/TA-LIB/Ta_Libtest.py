import pandas as pd
from sqlalchemy import create_engine
import talib


home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks5')
stocks =['300001','300002','300003','300004', '300005','300006','300007','300008','300009', '300010','300011','300012','300013','300014','300015','300016','300017','300018','300019']
for i, stock in enumerate(stocks):
    try:
        df = pd.read_sql(stock, eng)
        df.drop_duplicates(subset='datetime', keep='first',inplace=True)
        df.set_index('datetime', inplace=True)
        df.to_sql(stock, eng, if_exists='replace')
    except:
        pass