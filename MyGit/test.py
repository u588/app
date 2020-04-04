import random
from pyecharts import HeatMap
import pandas as pd


ConsName = '300银行'
df = pd.read_csv('f:/StocksData/Cons/' +ConsName + '.csv', index_col=0, dtype={'st_code':object})

dd = df[['open_chg', 'day_chg', 'close']].groupby(['day_chg', 'open_chg']).count().reset_index()
d =dd
X = df.groupby('day_chg').size().index.tolist()
Y = df.groupby('open_chg').size().index.tolist()
# data = dd.values.tolist()

chgs = dd.day_chg.tolist()
for i, chg in enumerate(chgs):
    d.loc[i, 'day_chg'] = X.index(dd.loc[i]['day_chg'])
    d.loc[i, 'open_chg'] = Y.index(dd.loc[i]['open_chg'])

data = d.values.tolist()

heatmap = HeatMap()
heatmap.add(
    "热力图直角坐标系",
    X,
    Y,
    data,
    is_visualmap=True,
    visual_text_color="#000",
    visual_orient="horizontal",
)
heatmap.render('f:/1.html')