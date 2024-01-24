from dask.distributed import LocalCluster

cluster = LocalCluster(ip='10.3.69.33',n_workers=2,memory_limit='8GiB')