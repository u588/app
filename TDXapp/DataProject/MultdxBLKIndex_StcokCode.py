import pandas as pd

dq = open('D:/new_tdx/T0002/export/地区板块.txt', 'r',encoding="GBK", errors='ignore').read()
fg = open('D:/new_tdx/T0002/export/风格板块.txt', 'r',encoding="GBK", errors='ignore').read()
gn = open('D:/new_tdx/T0002/export/概念板块.txt', 'r',encoding="GBK", errors='ignore').read()
hy = open('D:/new_tdx/T0002/export/行业板块.txt', 'r',encoding="GBK", errors='ignore').read()
zs = open('D:/new_tdx/T0002/export/指数板块.txt', 'r',encoding="GBK", errors='ignore').read()


def getCons(data, STL):
    dfi = pd.DataFrame(columns=['IndexCode', 'IndexName', 'StockCode', 'StockName','IndexSTL'])
    l = data.replace('\n','#').split('#')
    n = 0
    while n < len(l)-1:
        dfl = pd.DataFrame(l[n].split(',')).T
        dfl.columns=['IndexCode', 'IndexName', 'StockCode', 'StockName']
        dfi = pd.concat([dfi, dfl])
        n = n + 1
    dfi['IndexSTL'] = STL
    dfi.reset_index(drop=True, inplace=True)
    return dfi

data = [[dq,'地区'],[fg, '风格'], [gn, '概念'], [hy, '行业'], [zs, '指数']]
dfi = pd.DataFrame(columns=['IndexCode', 'IndexName', 'StockCode', 'StockName','IndexSTL'])

def Merg(res):
    global dfi
    a = res.result()
    dfi = pd.concat([dfi, a])
    return dfi

import pandas as pd
import concurrent.futures
#concurrent.futures主要实现了进程池和线程池，适合做派生一堆任务，异步执行完成后，再收集这些任务，且保持相同的api
def MultiGetIndexCons(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(getCons, task[0], task[1]).add_done_callback(Merg)


if __name__ == '__main__':
    MultiGetIndexCons(5,data)
    
    dfi.sort_values(by = ['IndexCode', 'StockCode'],ascending=True,ignore_index=True)\
    .set_index('IndexCode').to_excel('G:/Gitee/App/Data/2023TdxCs/tdxIndexsConsBLK.xlsx')

    dfs = dfi[['IndexCode','IndexName','IndexSTL']].drop_duplicates().reset_index(drop=True)
    dfs['Num'] = dfi.groupby('IndexCode').count()['IndexName'].reset_index(drop=True)
    dfs['From'] = 'TDXBLK'
    dfs.set_index('IndexCode').to_excel('G:/Gitee/App/Data/2023TdxCs/tdxIndexsBLK.xlsx')
     

    print('Index NormDescri finshed !')