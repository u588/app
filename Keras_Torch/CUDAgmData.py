import pandas as pd
import datetime
import time
from sqlalchemy import create_engine
from cuml.dask.cluster import DBSCAN
from dask.distributed import Client



# li =[[300,1],[300,2],[500,1],[500,2],[1000,1],[1000,2],[2000,1],[2000,2]]
li =[[1000,1],[1000,2],[2000,1],[2000,2]]
# li =[[500,2]]
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')
for gm in li:

    print('Read sql ')
    qq = pd.read_sql('qq'+str(gm[0]) + str(gm[1]), engAn)
    print(len(qq))
    b = pd.read_sql('b'+str(gm[0]) + str(gm[1]), engAn)
    
    X = (qq.fillna(1)).astype('float32')

    esp = 0.38
    n = 50
    client = Client('tcp://10.3.68.2:8786')
    while n > 5 :
        t0 = datetime.datetime.now()
        model = DBSCAN(client=client,verbose=True,eps=esp,min_samples=8)
        print('fit ESP8 : '+str(esp))
        yy = model.fit_predict(X)
        t1 = datetime.datetime.now()

        b['cluster'] = pd.DataFrame(yy)
        print(('b'+str(gm[0]) + str(gm[1])+'e'+str(esp)+'s8'))

        xx = b.sort_values('cluster').reset_index(drop=True)
        xxg = xx.groupby('cluster')

        cl = xxg.PCB5.describe().sort_values(['25%','mean'],ascending=False).round(2).reset_index()
        ccl = cl[cl['count']>1][cl['25%']>6].reset_index(drop=True)
        n = ccl.shape[0]
        print(n)
        print(ccl)
        print("\n")
        print("==============================================================")    

        if n > 40:
            esp = round(esp-0.1 , 3)
        elif n > 20:
            esp = round(esp-0.02 , 3)
        else:
            esp = round(esp-0.01, 3)
        
        if n < 21:
            b.set_index('code').to_sql(('b'+str(gm[0]) + str(gm[1])+'e'+str(esp)+'s8'),engAn, if_exists='replace')
            cl.to_sql(('b'+str(gm[0]) + str(gm[1])+'e'+str(esp)+'s8cl'),engAn, if_exists='replace')
        else:
            pass

        tt = int((t1-t0).total_seconds())
        print(tt)

    client.restart_workers(['GTX','P4-0','P4-1'])
    time.sleep(5)
client.close()
engAn.dispose()
print('client closed !')
print(client)
