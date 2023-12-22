import torch
import keras
from keras import layers
from keras import models
from keras.models import load_model
import numpy as np
import pandas as pd
import random
from sklearn.preprocessing import Normalizer
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import Counter
import matplotlib.pyplot as plt
import mplfinance as mpf

a = pd.read_excel('g:/1/2/st000001.xlsx')
b = pd.read_excel('g:/1/2/st000001pcb5.xlsx')
c = pd.read_excel('g:/1/2/st000001pcb13.xlsx')

#生成分析数据
#df.loc[(df.PCB13>-9)&(df.PCB13<-7),'classes'] = 10
i = 0
qq = pd.DataFrame((a[a.datetime>=b.loc[i][3:5][1]][a.datetime<=b.loc[i][3:5][0]].reset_index()[['open','close','high','low','mea']]).stack().values).T
while i < len(b):
    print(i)
    df = a[a.datetime>=b.loc[i][3:5][1]][a.datetime<=b.loc[i][3:5][0]].reset_index()[['open','close','high','low','mea']]
    aa = pd.DataFrame(df.stack().values).T
    qq = pd.concat([qq,aa])
    i = i + 1

# 归一化qq
qqq = ((qq-qq.min().min())/(qq.max().max()-qq.min().min())).reset_index(drop=True)

nor = Normalizer(norm='l2')
x_train = nor.fit_transform(qq[1:65])
x_test = nor.fit_transform(qq[65:])
X = nor.fit_transform(qq)

#选择合适的 n clusters 值
n_clusters=[2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,25,30,35,40,100]
for n_clusters in n_clusters:
    cluster=KMeans(n_clusters=n_clusters,random_state=1, n_init="auto")
    cluster_labels=cluster.fit_predict(X)
# 计算所有样本的平均轮廓系数
    silhouette=silhouette_score(X,cluster_labels)
    print("For n_clusters=",n_clusters, "ilhouette score is :", round(silhouette,2))

# 3D plot 
from matplotlib import  cm
from matplotlib.colors import LightSource
z = qqq.loc[0].values.reshape(14,5)
nrows, ncols = z.shape
x = np.linspace(0, 4, ncols)
x = np.linspace(0, 200, ncols)
y = np.linspace(0, 20, nrows)
y = np.linspace(0, 13, nrows)
x, y = np.meshgrid(x, y)

# region = np.s_[5:50, 5:50]
# x, y, z = x[region], y[region], z[region]

fig, ax = plt.subplots(subplot_kw=dict(projection='3d'))
ls = LightSource(270, 45)
rgb = ls.shade(z, cmap=cm.gist_earth, vert_exag=0.1, blend_mode='soft')
surf = ax.plot_surface(x, y, z, rstride=1, cstride=1, facecolors=rgb,linewidth=0, antialiased=False, shade=False)


# 平行坐标系
pd.plotting.parallel_coordinates(aaa[['open','close','high','low','mea','datetime']],'datetime')

#力矩图
#https://blog.csdn.net/qq_38998213/article/details/133015643
#https://www.mdpi.com/2227-9709/6/2/16
pd.plotting.radviz(df, 'Category')
