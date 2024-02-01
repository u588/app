import sys
# sys.getrecursionlimit()
sys.setrecursionlimit(2500)

import dask
from dask.distributed import config
dask.config.set({'distributed.scheduler.worker-ttl': '60 minutes'})

# dask.config.set({'distributed.scheduler.worker-ttl': None})
# dask.config.get("distributed.scheduler.worker-ttl")

# https://zhuanlan.zhihu.com/p/657368354 内存管理

from dask.distributed import Client
from dask_cuda import LocalCUDACluster
cluster = LocalCUDACluster(CUDA_VISIBLE_DEVICES='0,1',n_workers=2,threads_per_worker=8,ip='127.0.0.1',
                       dashboard_address='10.3.69.7:8787',worker_dashboard_address='10.3.69.7',memory_limit='25GB',
                       protocol='ucx',rmm_pool_size='7GB',enable_tcp_over_ucx=True,device_memory_limit="6GB",jit_unspill=True,
                        )


client = Client('ucx://10.3.69.6:8786')

import pandas as pd
from sqlalchemy import create_engine
from cuml.dask.cluster import DBSCAN

# import cudf

engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

qq = pd.read_sql('qq20001',engAn)
qq = qq.iloc[:,:36]
X = ((qq.astype('float32')).fillna(1)).values

# X = cudf.DataFrame(qq.fillna(1))

model = DBSCAN(eps=0.16,min_samples=8,output_type='pandas',)

yy = model.fit_predict(X)


from dask.distributed import Client
from dask_cuda import LocalCUDACluster
cluster = LocalCUDACluster(
    protocol="ucx",
    interface="lo",
    rmm_pool_size="6GB"
)
client = Client(cluster)






from dask_cuda import LocalCUDACluster
cluster = LocalCUDACluster(
    protocol="ucx",
    interface="lo",
    enable_tcp_over_ucx=True,
    # enable_nvlink=False,
    # enable_infiniband=True,
    # enable_rdmacm=True,
    rmm_pool_size="7GB"
)


b = pd.read_sql('b20001',engAn.connect())
b['cluster'] = yy
xx = b.sort_values('cluster').reset_index(drop=True)
xxg = xx.groupby('cluster')
xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).reset_index()