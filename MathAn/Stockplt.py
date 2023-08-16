import pandas as pd
import matplotlib.pyplot as plt
from sklearn import preprocessing
import mplfinance as mpf

from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

stockID = '601108'
df = pd.read_sql(stockID, eng).tail(233).reset_index(drop=True).reset_index()

fig, ax = plt.subplots()
ax.scatter(df['index'], df.close, s=preprocessing.minmax_scale(df.vol)*100, alpha=0.5)
plt.show()