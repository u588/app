import pandas as pd
from sqlalchemy import create_engine


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')

df = pd.read_excel('/home/ts/app/data/cicsClass.xlsx',dtype={'code':object})
df.exchange.replace('Shenzhen', 'sz', inplace=True)
df.exchange.replace('Shanghai', 'sh', inplace=True)
df.set_index('code').to_sql('cicsClass', eng , if_exists='replace')
