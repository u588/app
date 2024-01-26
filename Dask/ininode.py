from dask.distributed import LocalCluster
from dask_cuda import LocalCUDACluster
cluster = LocalCluster(name='dask_6',n_workers=0,threads_per_worker=1,ip='10.3.69.7',scheduler_port='8786',
                       dashboard_address='10.3.69.7:8787',worker_dashboard_address='10.3.69.7',memory_limit='8GiB',
                       )
cluster = LocalCluster(name='dask_6',n_workers=2,threads_per_worker=1,ip='10.3.69.6',scheduler_port='8786',
                       dashboard_address='10.3.69.6:8787',worker_dashboard_address='10.3.69.6',memory_limit='8GiB',
                       )
cluster = LocalCUDACluster(name='dask_6',CUDA_VISIBLE_DEVICES='0,1',n_workers=2,threads_per_worker=1,ip='10.3.69.7',scheduler_port='8786',
                       dashboard_address='10.3.69.7:8787',worker_dashboard_address='10.3.69.7',memory_limit='15GB',device_memory_limit=0.9,
                       protocol='tcp',
                       )
cluster = LocalCUDACluster(name='dask_6',CUDA_VISIBLE_DEVICES='0',n_workers=1,threads_per_worker=1,ip='10.3.69.6',scheduler_port='8786',
                       dashboard_address='10.3.69.6:8787',worker_dashboard_address='10.3.69.6',memory_limit='15GB',device_memory_limit=0.9,
                       protocol='tcp',
                       )

