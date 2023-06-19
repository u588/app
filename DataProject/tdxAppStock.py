import json
import re
import pandas as pd

a = open('D:/new_tdx/T0002/hq_cache/infoharbor_ex.code', 'r',encoding="GBK").read()
l = a.replace('\n','#').split('#')

q = pd.DataFrame(['a','b']).T
n = 0
while n < len(l):
    try:
        df = pd.DataFrame(l[n].split('|')[:2]).T
        q = pd.concat([q, df])
        n = n + 1
        print(str(n) + '  concat !')
    except:
        n = n + 1
        print(str(n) + '  pass !')
        pass

q.reset_index(drop=True, inplace=True)
q.drop(0, inplace=True)
q.dropna(inplace=True)
q.columns = ['StockCode', 'StockName']

q.set_index('StockCode').to_excel('G:/Gitee/App/Data/2023TdxCs/StockCodeApp.xlsx')