from dask.distributed import LocalCluster

cluster = LocalCluster(name='dask_6',n_workers=0,threads_per_worker=1,ip='10.3.69.7',scheduler_port='8786',
                       dashboard_address='10.3.69.7:8787',worker_dashboard_address='10.3.69.7',memory_limit='8GiB',
                       )
cluster = LocalCluster(name='dask_6',n_workers=2,threads_per_worker=1,ip='10.3.69.6',scheduler_port='8786',
                       dashboard_address='10.3.69.6:8787',worker_dashboard_address='10.3.69.6',memory_limit='8GiB',
                       )


from dask_cuda import LocalCUDACluster
cluster = LocalCUDACluster(name='dask_6',CUDA_VISIBLE_DEVICES='0,1',n_workers=2,threads_per_worker=1,ip='10.3.69.7',scheduler_port='8786',
                       dashboard_address='10.3.69.7:8787',worker_dashboard_address='10.3.69.7',memory_limit='15GB',device_memory_limit=0.9,
                       protocol='ucx',rmm_pool_size='7GB',
                       )
cluster = LocalCUDACluster(name='dask_6',CUDA_VISIBLE_DEVICES='0,1',n_workers=2,threads_per_worker=1,ip='10.3.69.7',scheduler_port='8786',
                       dashboard_address='10.3.69.7:8787',worker_dashboard_address='10.3.69.7',)

from dask_cuda import LocalCUDACluster
cluster = LocalCUDACluster(name='GTX',CUDA_VISIBLE_DEVICES='0',n_workers=1,threads_per_worker=1,ip='10.3.68.2',scheduler_port='8786',
                       dashboard_address='10.3.62.2:8787',worker_dashboard_address='10.3.62.2',memory_limit='25GB',device_memory_limit='7GB',
                       protocol='ucx',
                       )

