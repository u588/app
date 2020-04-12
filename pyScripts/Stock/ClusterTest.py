import sys 
from datetime import datetime 
import matplotlib as mpl
import time 
import pandas as pd 
import numpy as np 
import matplotlib.pyplot as plt 
from matplotlib.collections import LineCollection 
from sklearn import cluster, covariance, manifold 


mpl.rcParams['font.sans-serif'] = ['KaiTi'] # 指定默认字体
mpl.rcParams['axes.unicode_minus'] = False # 解决保存图像是负号'-'显示为方块的问题
plt.style.use({'figure.figsize':(18, 9)})

from sqlalchemy import create_engine

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')

IndexCode = '399394'

IndexConsts = pd.read_csv('f:\indexconst.csv', dtype={'code':object, 'index_code':object})
symbol_dict = IndexConsts[IndexConsts.index_code==IndexCode][['code', 'name']]

d1 = '2018-01-01'
d2 = '2018-12-22'

start_date = datetime.strptime(d1,'%Y-%m-%d')
end_date = datetime.strptime(d2,'%Y-%m-%d')




# start_date = datetime.strptime("2015-06-29", "%Y-%m-%d") 
# end_date = datetime.strptime("2018-06-29", "%Y-%m-%d")

#eng = sqlite3.connect("C:\\Users\\humingj\\Desktop\\jhm\\scrapetest\\mydb.db") 
#symbol_dict = pd.read_sql('select code,name from list_shang_zheng_50', eng) 
#symbol_dict = pd.read_sql('select code,name from list_hu_shen_300', eng)

symbols, names = np.array(symbol_dict[['code','name']].values).T 
quotes = pd.read_csv('f:/stocksone.csv')
df = quotes[symbols]
df['datetime'] = quotes.datetime

dd = df[(df['datetime']>d1) & (df['datetime']<d2)]
dd.fillna(method='ffill')
dd.set_index('datetime', inplace=True)


# for symbol in symbols: #print('Fetching quote history for %r' % symbol)
#     try: 
#         quotes.append(quotes_historical_google(symbol , start_date, end_date)) 
#     except Exception as e:
#         print(e) 
#         pass

# close_prices = np.vstack([q['close'] for q in quotes]) 
# open_prices = np.vstack([q['open'] for q in quotes]) 
# # The daily variations of the quotes are what carry most information

var = dd.copy()
# Learn a graphical structure from the correlations
edge_model = covariance.GraphLassoCV()
# standardize the time series: using correlations rather than covariance
# is more efficient for structure recovery

X = var/var.std(axis=0) 
edge_model.fit(X) 

# Cluster using affinity propagation
_, labels = cluster.affinity_propagation(edge_model.covariance_) 
n_labels = labels.max() 

for i in range(n_labels + 1): 
    print('Cluster %i: %s' % ((i + 1), ', '.join(names[labels == i]))) 
# #############################################################################
# Find a low-dimension embedding for visualization: find the best position of
# the nodes (the stocks) on a 2D plane

# We use a dense eigen_solver to achieve reproducibility (arpack is
# initiated with random vectors that we don't control). In addition, we
# use a large number of neighbors to capture the large-scale structure.
node_position_model = manifold.LocallyLinearEmbedding( n_components=2, eigen_solver='dense', n_neighbors=6) 
embedding = node_position_model.fit_transform(X.T).T 

# #############################################################################
# Visualization
plt.figure(1, facecolor='w', figsize=(10, 8)) 
plt.clf() 
ax = plt.axes([0., 0., 1., 1.]) 
plt.axis('off') 

# Display a graph of the partial correlations
partial_correlations = edge_model.precision_.copy() 
d = 1 / np.sqrt(np.diag(partial_correlations)) 
partial_correlations *= d 
partial_correlations *= d[:, np.newaxis] 
non_zero = (np.abs(np.triu(partial_correlations, k=1)) > 0.02) 

# Plot the nodes using the coordinates of our embedding
plt.scatter(embedding[0], embedding[1], s=100 * d ** 2, c=labels,
            cmap=plt.cm.Spectral) 
# Plot the edges
start_idx, end_idx = np.where(non_zero) 
# a sequence of (*line0*, *line1*, *line2*), where::
#            linen = (x0, y0), (x1, y1), ... (xm, ym)
segments = [[embedding[:, start], embedding[:, stop]] for start, stop in zip(start_idx, end_idx)] 
values = np.abs(partial_correlations[non_zero]) 
lc = LineCollection(segments,
                    zorder=0, cmap=plt.cm.hot_r,
                    norm=plt.Normalize(0, .7 * values.max())) 

lc.set_array(values) 
lc.set_linewidths(15 * values) 
ax.add_collection(lc) 

# Add a label to each node. The challenge here is that we want to
# position the labels to avoid overlap with other labels
for index, (name, label, (x, y)) in enumerate( zip(names, labels, embedding.T)): 
    dx = x - embedding[0] 
    dx[index] = 1
    dy = y - embedding[1] 
    dy[index] = 1
    this_dx = dx[np.argmin(np.abs(dy))] 
    this_dy = dy[np.argmin(np.abs(dx))] 
    if this_dx > 0: 
        horizontalalignment = 'left'
        x = x + .002
    else: 
        horizontalalignment = 'right'
        x = x - .002
    if this_dy > 0: 
        verticalalignment = 'bottom'
        y = y + .002
    else: 
        verticalalignment = 'top'
        y = y - .002
    plt.text(x, y, name, size=10,
             horizontalalignment=horizontalalignment,
             verticalalignment=verticalalignment,
             bbox=dict(facecolor='w',
                       edgecolor=plt.cm.Spectral(label / float(n_labels)),
                       alpha=.6)) 
plt.xlim(embedding[0].min() - .15 * embedding[0].ptp(),
         embedding[0].max() + .10 * embedding[0].ptp(),) 
plt.ylim(embedding[1].min() - .03 * embedding[1].ptp(),
         embedding[1].max() + .03 * embedding[1].ptp()) 
plt.show()
