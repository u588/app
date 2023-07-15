import pandas as pd
import numpy as np
import seaborn as sns
from mpl_toolkits.mplot3d.axes3d import Axes3D
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams['font.sans-serif'] = ['KaiTi']


ConsName = '中证水泥'
df = pd.read_excel('G:\Gitee\App\MathAn\ell.xlsx')
# df['open_round'] = df.open_chg.round(0)
# df['day_round'] = df.day_chg.round(0)

dd = df[['open_chg', 'day_chg', 'close']].groupby(['day_chg', 'open_chg']).count().reset_index()
# dd = df[['open_round', 'day_round', 'close']].groupby(['day_round', 'open_round']).count().reset_index()

# dd.to_csv('f:/group.csv')
# data = dd.set_index('open_chg')

pt = dd.pivot(index='open_chg', columns='day_chg', values='close')
# pt = dd.pivot(index='open_round', columns='day_round', values='close')
f, ax = plt.subplots(figsize = (16,9))


g = sns.scatterplot(x='stb', y='am', hue='eq', style='eq',data= df)
g.set(xscale="log", yscale="log")
g.ax.xaxis.grid(True, "minor", linewidth=.25)
g.ax.yaxis.grid(True, "minor", linewidth=.25)
g.despine(left=True, bottom=True)

plt.show()