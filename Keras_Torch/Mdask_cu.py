
from dask_cuda import LocalCUDACluster
cluster = LocalCUDACluster(name='dask_6',CUDA_VISIBLE_DEVICES='0,1',n_workers=2,threads_per_worker=1,ip='127.0.0.1',scheduler_port='8786',
                       dashboard_address='10.3.69.7:8787',worker_dashboard_address='10.3.69.7',memory_limit='15GB',device_memory_limit=0.9,
                       protocol='ucx',rmm_pool_size='7GB',
                        )
# protocol='ucx'enable_tcp_over_ucx=True,
                      

import dask
from dask.distributed import config
dask.config.set({'distributed.scheduler.worker-ttl': None})
dask.config.set({'distributed.scheduler.worker-ttl': '30 minutes'})
dask.config.get("distributed.scheduler.worker-ttl")

import pandas as pd
from sqlalchemy import create_engine
from cuml.dask.cluster import DBSCAN
# from dask.distributed import Client
# import cudf

# client = Client('ucx://127.0.0.1:36379')
# client = Client('tcp://127.0.0.1:8786')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

qq = pd.read_sql('qq20001',engAn.connect())
qq = qq.iloc[:,:36]
X = ((qq.astype('float32')).fillna(1)).values

# X = cudf.DataFrame(qq.fillna(1))

model = DBSCAN(eps=0.27,min_samples=5)

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