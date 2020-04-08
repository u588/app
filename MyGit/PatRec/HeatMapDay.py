import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib as mpl
from sqlalchemy import create_engine


engD = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
eng5 = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks5')

StockCode = '600624'

D = pd.read_sql(StockCode, engD)
D5 = pd.read_sql(StockCode, eng5)
DateLists = D.datetime.tolist()

for i, Date in enumerate (DateLists):
    try:
        df = D5[(D5.datetime >DateLists[i][:10]) & (D5.datetime < DateLists[(i+1)][:10])].set_index('datetime')
        D.loc[i, 'h_time']=df.high.idxmax()[10:]
        D.loc[i, 'l_time']=df.low.idxmin()[10:]
        # D.to_csv('f:/lhtme.csv')
    except:
        pass

mpl.rcParams['font.sans-serif'] = ['KaiTi']
dd = D[['h_time', 'l_time', 'close']].groupby(['l_time', 'h_time']).count().reset_index()
dd.to_csv('f:/hl.csv')
D.to_csv('f:/D1.csv')
pt = dd.pivot(index='l_time', columns='h_time', values='close')

f, ax = plt.subplots(figsize = (13,6.5))
plt.subplots_adjust(left=0.1 ,bottom=0.12,right=1, top=0.96, wspace=0.2, hspace=0.2)
 
sns.heatmap(pt, cmap = 'cool',linewidths=0.1, linecolor=(0.1, 0.2, 0.5, 0.05),annot=True)   
ax.set_title(StockCode)
ax.set_xlabel('High_time')
ax.set_ylabel('Low_time')

plt.show()