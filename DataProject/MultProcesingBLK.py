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


import multiprocessing


if __name__ == '__main__':
 
    dfi = pd.DataFrame(columns=['IndexCode', 'IndexName', 'StockCode', 'StockName','IndexSTL'])

    pool  = multiprocessing.Pool(processes=5)
    results = []
    for i in [0, 1, 2,3,4]:
        results.append(pool.apply_async(getCons, (data[i][0], data[i][1]) ))
    pool.close()
    pool.join()
    
    for res in results:
        dfi = pd.concat([dfi, res.get()])
   
    dfi.sort_values(by = ['IndexCode', 'StockCode'],ascending=True,ignore_index=True)\
    .set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/tdxIndexsConsBLK.xlsx')

    dfs = dfi[['IndexCode','IndexName','IndexSTL']].drop_duplicates().reset_index(drop=True)
    n = 0
    while n < dfs.shape[0]:
        dfs.loc[[n],['Num']] = len(dfi.groupby('IndexCode').groups[dfs.loc[n][0]])
        n = n + 1
        print(str(n) + '  ok !') 
 
    dfs['From'] = 'TDXBLK'
    dfs.set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/tdxIndexsBLK.xlsx')
   


    print('========= Finshed !')