import cudf
from cuml.cluster import DBSCAN

# Create and populate a GPU DataFrame
gdf_float = cudf.DataFrame()
gdf_float['0'] = [1.0, 2.0, 5.0]
gdf_float['1'] = [4.0, 2.0, 1.0]
gdf_float['2'] = [4.0, 2.0, 1.0]

# Setup and fit clusters
dbscan_float = DBSCAN(eps=1.0, min_samples=1)
dbscan_float.fit(gdf_float)

print(dbscan_float.labels_)


# Initialize UCX for high-speed transport of CUDA arrays
from dask_cuda import LocalCUDACluster

# Create a Dask single-node CUDA cluster w/ one worker per device
cluster = LocalCUDACluster(protocol="ucx",
                           enable_tcp_over_ucx=True,
                           enable_nvlink=True,
                           enable_infiniband=False)

