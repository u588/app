import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import MeanShift, estimate_bandwidth
from sklearn.datasets import make_blobs

from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
df = pd.read_sql('600180', eng).tail(5360).reset_index(drop=True)



# The following bandwidth can be automatically detected using
bandwidth = estimate_bandwidth(X, quantile=0.2, n_samples=20)

ms = MeanShift(bandwidth=bandwidth, bin_seeding=True)
ms.fit(X)
labels = ms.labels_
cluster_centers = ms.cluster_centers_

labels_unique = np.unique(labels)
n_clusters_ = len(labels_unique)

print("number of estimated clusters : %d" % n_clusters_)

plt.figure(1)
plt.clf()

# https://matplotlib.org/stable/api/markers_api.html#module-matplotlib.markers
colors = ['#dede00', '#377eb8', '#f781bf', '#377110', '#f71921', '#de000a','#382916']
markers = ["x", "o", "^","*","D","d","+"]

for k, col in zip(range(n_clusters_), colors):
    my_members = labels == k
    cluster_center = cluster_centers[k]
    plt.plot(X[my_members, 0], X[my_members, 1], markers[k], color=col)
    plt.plot(
        cluster_center[0],
        cluster_center[1],
        markers[k],
        markerfacecolor=col,
        markeredgecolor="k",
        markersize=14,
    )
plt.title("Estimated number of clusters: %d" % n_clusters_)
plt.show()