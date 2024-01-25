from dask.distributed import Client

client = Client("10.3.69.7:8786")

def get_gpu_model():
    import pynvml
    pynvml.nvmlInit()
    return pynvml.nvmlDeviceGetName(pynvml.nvmlDeviceGetHandleByIndex(0))

def main():
    cluster = LocalCUDACluster()
    client = Client(cluster)
    # client = Client("10.3.69.6:8786")
    result = client.submit(get_gpu_model).result()
    print(f"{result=}")

if __name__ == "__main__":
    main()