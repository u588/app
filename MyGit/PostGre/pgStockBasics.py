from sqlalchemy import create_engine
import tushare as ts


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockFund')


#股票基本信息
df = ts.get_stock_basics()
df.to_sql('StockBas',eng, if_exists='replace')
print('股票基本信息 ok')
