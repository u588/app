import pandas as pd
# import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams['font.sans-serif'] = ['KaiTi']


ConsName = '中证水泥'
df = pd.read_excel('G:\Gitee\App\MathAn\el.xlsx')
# df['open_round'] = df.open_chg.round(0)
# df['day_round'] = df.day_chg.round(0)

# dd = df[['open_chg', 'day_chg', 'close']].groupby(['day_chg', 'open_chg']).count().reset_index()
# # dd = df[['open_round', 'day_round', 'close']].groupby(['day_round', 'open_round']).count().reset_index()

# # dd.to_csv('f:/group.csv')
# # data = dd.set_index('open_chg')

# pt = dd.pivot(index='open_chg', columns='day_chg', values='close')
# # pt = dd.pivot(index='open_round', columns='day_round', values='close')
# f, ax = plt.subplots(figsize = (16,9))
dd = df

g = sns.scatterplot(x='stb', y='am', hue='eq', style='eq',size='eoc' ,data= df)
g.set(xscale="log", yscale="log")
g.set(xlabel='电视用户数量')
g.set(xlabel='宽带用户数量')
g.set(ylabel='电费金额')
g.xaxis.grid(True, "minor", linewidth=.25)
g.yaxis.grid(True, "minor", linewidth=.25)
g.despine(left=True, bottom=True)

plt.show()

========== 回归分析 ========
import statsmodels.api as sm
x = df.groupby('eq').get_group('EOC')[['stb','pc','eoc']].fillna(0)
x = df.groupby('eq').get_group('N')[['stb']].fillna(0)
y = df.groupby('eq').get_group('EOC')['am']

x = sm.add_constant(x)
model = sm.OLS(y, x) 

results = model.fit()
results.summary()


-------- sklearn ------
from sklearn import linear_model

regr = linear_model.LinearRegression()
regr.fit(x,y)
regr.coef_


======== 数据标准化 =============
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
df_scaled = scaler.fit_transform(df)