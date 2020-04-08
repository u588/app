import pandas as pd
from pyecharts import HeatMap, Overlap, Grid
import data_fq  as fq
from sqlalchemy import create_engine


engS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engX = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxXdXr')

StockCode = '002017'

D = pd.read_sql(StockCode, engS)
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


df = data
dd = df[['open_chg', 'day_chg', 'close']].groupby(['day_chg', 'open_chg']).count().reset_index()
dh = df[['open_chg', 'day_H', 'close']].groupby(['day_H', 'open_chg']).count().reset_index()
dl = df[['open_chg', 'day_L', 'close']].groupby(['day_L', 'open_chg']).count().reset_index()

d =dd
X = df.groupby('day_chg').size().index.tolist()
Y = df.groupby('open_chg').size().index.tolist()
# data = dd.values.tolist()
ma = dd.close.max()
chgs = dd.day_chg.tolist()
for i, chg in enumerate(chgs):
    d.loc[i, 'day_chg'] = X.index(dd.loc[i]['day_chg'])
    d.loc[i, 'open_chg'] = Y.index(dd.loc[i]['open_chg'])

data = d.values.tolist()

heatmap = HeatMap(height=600, width=1300, page_title= StockCode)
heatmap.add("热力图直角坐标系", X, Y, data,
    is_visualmap=True,
    visual_text_color="#000",
    visual_orient="horizontal",
    visual_range = [0,ma]
)
heatmap.render('F:/WWWstocks/'+ StockCode + '.html')
print('ok !')
