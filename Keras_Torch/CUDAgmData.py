import pandas as pd
import time
from sqlalchemy import create_engine
from cuml.dask.cluster import DBSCAN
from dask.distributed import Client

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

li =[[300,1],[300,2],[500,1],[500,2],[1000,1],[1000,2],[2000,1],[2000,2]]

print('Read sql ')
qq = pd.read_sql('qq20001', engAn)
b = pd.read_sql('b20001', engAn)
X = qq.astype('float32')

client = Client('tcp://10.3.68.3:8786')

# ============ minSamples 3
esp = 0.3
n = 200
while n > 100 :
    model = DBSCAN(client=client,verbose=True,eps=esp,min_samples=5)
    print('fit ESP5 : '+str(esp))
    yy = model.fit_predict(X)
    n = pd.DataFrame(yy).groupby(0).size().shape[0]
    print("==> "+str(n))
    b['cluster'] = pd.DataFrame(yy)
    # b.set_index('code').to_sql(('CUDAe'+str(esp)+'s3b'+filname),engAn, if_exists='replace')
    xx = b.sort_values('cluster').reset_index(drop=True)
    xxg = xx.groupby('cluster')
    xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).reset_index()
    cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()
    print(cl)
    print("\n")
    print("==============================================================")    
    # cl.to_sql(('e'+str(esp)+'s3bcl'+filname),engAn, if_exists='replace')
    if n > 500:
        esp = round(esp-0.1 , 2)
    else:
        esp = round(esp-0.02, 2)

#=========== minSamples 5

esp = 0.3
n = 300
while n > 100 :
    
    model = DBSCAN(client=client,verbose=True,eps=esp,min_samples=8)
    print('fit ESP8 : '+str(esp))
    yy = model.fit_predict(X)
    n = pd.DataFrame(yy).groupby(0).size().shape[0]
    print("==> "+str(n))
    b['cluster'] = pd.DataFrame(yy)
    # b.set_index('code').to_sql(('CUDAe'+str(esp)+'s5b'+filname),engAn, if_exists='replace')
    xx = b.sort_values('cluster').reset_index(drop=True)
    xxg = xx.groupby('cluster')
    xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).reset_index()
    cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()
    print(cl)
    print("\n")
    print("==============================================================")
    # cl.to_sql(('CUDAe'+str(esp)+'s5bcl'+filname),engAn, if_exists='replace')
    if n > 500:
        esp = round(esp-0.1, 2)
    else:
        esp = round(esp-0.02 , 2)

    # client.restart_workers(['GTX','P4-0','P4-1'])
    # time.sleep(5)


client.close()
print('client closed !')
print(client)
time.sleep(5)