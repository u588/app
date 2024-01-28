# https://docs.rapids.ai/api/cuml/stable/api/#cuml.DBSCAN


import pandas as pd
from sqlalchemy import create_engine
# from cuml import DBSCAN
# from cuml.cluster import DBSCAN
from cuml.dask.cluster import DBSCAN

from dask_cuda import LocalCUDACluster
from dask.distributed import Client
import dask

import cudf

# Initialize UCX for high-speed transport of CUDA arrays
from dask_cuda import LocalCUDACluster

# Create a Dask single-node CUDA cluster w/ one worker per device
cluster = LocalCUDACluster(protocol="tcp",
                           enable_tcp_over_ucx=False,
                           enable_nvlink=False,
                           enable_infiniband=False)

cluster = LocalCUDACluster(CUDA_VISIBLE_DEVICES="0,1")
client = Client(cluster)



engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

qq = pd.read_sql('qq3002',engAn.connect())

X = cudf.DataFrame(qq.fillna(1))
X = ((qq.astype('float32')).fillna(1)).values

model = DBSCAN(eps=0.48,min_samples=3)

yy = model.fit_predict(X)

b['cluster'] = pd.DataFrame(yy)
xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')
print(xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False))



client.close()
cluster.close()
