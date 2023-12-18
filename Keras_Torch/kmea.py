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

a = pd.read_excel('g:/1/2/st000001.xlsx')
b = pd.read_excel('g:/1/2/st000001pcb5.xlsx')
c = pd.read_excel('g:/1/2/st000001pcb13.xlsx')

i = 0
qq = pd.DataFrame((a[a.datetime>=b.loc[i][3:5][1]][a.datetime<=b.loc[i][3:5][0]].reset_index()[['open','close','high','low','mea']]).stack().values).T
while i < len(b):
    print(i)
    df = a[a.datetime>=b.loc[i][3:5][1]][a.datetime<=b.loc[i][3:5][0]].reset_index()[['open','close','high','low','mea']]
    aa = pd.DataFrame(df.stack().values).T
    qq = pd.concat([qq,aa])
    i = i + 1

nor = Normalizer(norm='l2')
x_train = nor.fit_transform(qq[1:65])
x_test = nor.fit_transform(qq[65:])
X = nor.fit_transform(qq)

#选择合适的 n clusters 值
n_clusters=[2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
for n_clusters in n_clusters:
    cluster=KMeans(n_clusters=n_clusters,random_state=1, n_init="auto")
    cluster_labels=cluster.fit_predict(X)
# 计算所有样本的平均轮廓系数
    silhouette=silhouette_score(X,cluster_labels)
    print("For n_clusters=",n_clusters, "ilhouette score is :", round(silhouette,2))