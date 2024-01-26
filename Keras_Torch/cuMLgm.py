import pandas as pd
from sqlalchemy import create_engine
from cuml import DBSCAN
from cuml.cluster import DBSCAN

import cudf

engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

qq = pd.read_sql('qq3001',engAn.connect())

X = cudf.DataFrame(qq.fillna(1))
model = DBSCAN(eps=0.27,min_samples=5)

yy = model.fit_predict(X)

b['cluster'] = pd.DataFrame(yy)
xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')
print(xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False))

