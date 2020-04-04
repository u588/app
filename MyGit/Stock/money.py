from sqlalchemy import create_engine
import pandas as pd
import matplotlib.pyplot as plt

home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = home

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/MarkCap')

df = pd.read_sql('HsgtFlow', eng)
df.trade_date = pd.to_datetime(df.trade_date)
df.set_index('trade_date', inplace=True)
df[['north_money','south_money']].plot()
plt.show()

