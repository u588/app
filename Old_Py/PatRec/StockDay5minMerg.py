import pandas as pd
import seaborn as sns
import data_fq  as fq
import matplotlib.pyplot as plt
import matplotlib as mpl
from sqlalchemy import create_engine


engD = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
eng5 = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks5')
engX = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxXdXr')

StockCode = '002364'

D = pd.read_sql(StockCode, engD)
Data = D[D.datetime>'2000-01-01']
X = pd.read_sql(StockCode, engX)
XdXr = X[X.year>1999]

data = fq.qfq(Data, XdXr)[['open', 'high', 'low', 'close', 'vol']].tail(-10).reset_index()

data['pre_close']=data.close.shift(1)

data['pc_chg']=(((data.close-data.pre_close)/data.pre_close)*100).round(1)
data['open_chg']=(((data.open-data.pre_close)/data.pre_close)*100).round(1)
data['day_chg']=(((data.close-data.open)/data.open)*100).round(1)
data['day_H'] = (((data.high-data.open)/data.open)*100).round(1)
data['day_L'] = (((data.low-data.open)/data.open)*100).round(1)


D = data
D5 = pd.read_sql(StockCode, eng5)
DateLists = D.datetime.astype(str).tolist()

for i, Date in enumerate (DateLists):
    try:
        df = D5[(D5.datetime >DateLists[i][:10]) & (D5.datetime < DateLists[(i+1)][:10])].set_index('datetime')
        D.loc[i, 'h_time']=df.high.idxmax()[10:]
        D.loc[i, 'l_time']=df.low.idxmin()[10:]
        # D.to_csv('f:/lhtme.csv')
    except:
        pass

# mpl.rcParams['font.sans-serif'] = ['KaiTi']
# dd = D[['h_time', 'l_time', 'close']].groupby(['l_time', 'h_time']).count().reset_index()
# dd.to_csv('f:/hl.csv')

D.to_csv('f:/D.csv')

# pt = dd.pivot(index='l_time', columns='h_time', values='close')

# f, ax = plt.subplots(figsize = (13,6.5))
# plt.subplots_adjust(left=0.1 ,bottom=0.12,right=1, top=0.96, wspace=0.2, hspace=0.2)
 
# sns.heatmap(pt, cmap = 'cool',linewidths=0.1, linecolor=(0.1, 0.2, 0.5, 0.05),annot=True)   
# ax.set_title(StockCode)
# ax.set_xlabel('High_time')
# ax.set_ylabel('Low_time')

# plt.show()