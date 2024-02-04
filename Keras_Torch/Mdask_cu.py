import sys
# sys.getrecursionlimit()
sys.setrecursionlimit(2500)

import dask
from dask.distributed import config
dask.config.set({'distributed.scheduler.worker-ttl': '60 minutes'})

# dask.config.set({'distributed.scheduler.worker-ttl': None})
# dask.config.get("distributed.scheduler.worker-ttl")

# https://zhuanlan.zhihu.com/p/657368354 内存管理

import os

os.environ["UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES"] = "cuda"
os.environ["DASK_DISTRIBUTED__COMM__UCX__CREATE_CUDA_CONTEXT"] = "True"

from dask.distributed import Client

client = Client('ucx://10.3.68.2:8786')

from dask_cuda import LocalCUDACluster
cluster = LocalCUDACluster(CUDA_VISIBLE_DEVICES='0',n_workers=1,threads_per_worker=2,host='10.3.68.2',scheduler_port='8786',
                       dashboard_address='10.3.68.2:8787',worker_dashboard_address='10.3.68.2',memory_limit='20GB',
                       protocol='ucx',rmm_pool_size='7GB',device_memory_limit="6GB",local_directory="/home/ts/cudatmp",
                        )


# client = Client('ucx://10.3.68.3:8786')

import pandas as pd
from sqlalchemy import create_engine
from cuml.dask.cluster import DBSCAN

# import cudf

engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

qq = pd.read_sql('qq20001',engAn)
qq = qq.iloc[:,:36]
X = qq.astype('float32')

X = ((qq.astype('float32')).fillna(1)).values

# X = cudf.DataFrame(qq.fillna(1))


model = DBSCAN(client=client,verbose=True, eps=0.16,min_samples=8)
yy = model.fit_predict(X)



model = DBSCAN(client=client,verbose=True, eps=0.16,min_samples=8,output_type='pandas',)



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