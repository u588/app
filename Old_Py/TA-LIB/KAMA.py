import pandas as pd
from sqlalchemy import create_engine
import matplotlib.pyplot as plt


home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs')

code= '000001'

n=10
fast_n=2
slow_n=30

df = pd.read_sql(code, eng)

df['change']=abs(df['close']-df['close'].shift(n))
#Change = ABS(Close - Close (10 periods ago)) 
#Change = abs(df['close']-df['close'][-n])
#Volatility = Sum10(ABS(Close - Prior Close))
df['volatility']=abs(df['close']-df['close'].shift(1)).rolling(n).sum()
df['ER']=df['change']/df['volatility']
fastest = 2.0 / (fast_n + 1)
slowest = 2.0 / (slow_n + 1)
delta = fastest - slowest
df['SC']=(df['ER']*delta + slowest)*(df['ER']*delta + slowest)

