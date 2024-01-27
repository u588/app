# qq.astype('float32') 数据转 单精度
# qq = qq.iloc[:,:36] 去前几列



import pandas as pd
from sqlalchemy import create_engine
# from cuml import DBSCAN
from cuml.cluster import DBSCAN
from cuml.common.device_selection import using_device_type, set_global_device_type
set_global_device_type("CPU")
import cudf

engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

qq = pd.read_sql('qq3001',engAn.connect())

X = cudf.DataFrame(qq.fillna(1))
X = qq.fillna(1).values
model = DBSCAN(eps=0.27,min_samples=5)

yy = model.fit_predict(X)
b = pd.DataFrame()
b['cluster'] = pd.DataFrame(yy.to_numpy())
xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')
print(xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False))

