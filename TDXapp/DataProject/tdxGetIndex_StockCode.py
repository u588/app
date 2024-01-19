import re
import pandas as pd

sh = open('D:/new_tdx/T0002/hq_cache/shm.tnf', 'r',encoding="GBK", errors='ignore').read()
sz = open('D:/new_tdx/T0002/hq_cache/szm.tnf', 'r',encoding="GBK", errors='ignore').read()
zz = pd.read_excel('D:/new_tdx/T0002/export/zzIndexs.xlsx', dtype={'IndexCode':object})


shIndex00 = re.findall("00\d{4}.{30}", sh)
shIndex88 = re.findall("88\d{4}.{30}", sh)
shStock60 = re.findall("60\d{4}.{30}", sh)
shStock68 = re.findall("68\d{4}.{30}", sh)

szIndex39 = re.findall("39\d{4}.{30}", sz)
szStock00 = re.findall("00\d{4}.{30}", sz)
szStock30 = re.findall("30\d{4}.{30}", sz)


DataStock = [ shStock60, shStock68, szStock00, szStock30]
qq = pd.DataFrame(['a','b']).T
for l in DataStock:
    q = pd.DataFrame(['a','b']).T
    n = 0
    while n < len(l):
        try:
            df = pd.DataFrame(re.sub(r'#+', '#', l[n].replace('\x00', '#').replace(' ','').replace('Ａ', 'A')).split('#')[:2]).T
            q = pd.concat([q, df])
            n = n + 1
            # print(str(n) + '  concat !')
        except:
            n = n + 1
            print(str(n) + '  pass !')
            pass
    q.reset_index(drop=True, inplace=True)
    q.drop(0, inplace=True)
    q.dropna(inplace=True)
    qq = pd.concat([qq, q])
qq.reset_index(drop=True, inplace=True)
qq.drop(0, inplace=True)
qq.dropna(inplace=True)
qq.columns = ['StockCode', 'StockName'] 
qq.sort_values(by = 'StockCode' ,ascending=True,ignore_index=True)\
               .set_index('StockCode').to_excel('G:/Gitee/App/tdxAppData/tdxSocksCode.xlsx')
print('=============> Stock ok !')

DataIndex = [shIndex00, shIndex88, szIndex39]
qq = pd.DataFrame(['a','b']).T
for l in DataIndex:
    q = pd.DataFrame(['a','b']).T
    n = 0
    while n < len(l):
        try:
            df = pd.DataFrame(re.sub(r'#+', '#',\
                                     l[n].replace('\x00', '#').replace(' ','').replace('Ａ', 'A'))\
                                     .split('#')[:2]).T
            q = pd.concat([q, df])
            n = n + 1
            # print(str(n) + '  concat !')
        except:
            n = n + 1
            print(str(n) + '  pass !')
            pass
    q.reset_index(drop=True, inplace=True)
    q.drop(0, inplace=True)
    q.dropna(inplace=True)
    qq = pd.concat([qq, q])

qq.reset_index(drop=True, inplace=True)
qq.drop(0, inplace=True)
qq.dropna(inplace=True)
qq.columns = ['IndexCode', 'IndexName'] 
qq = pd.concat([qq, zz]).drop_duplicates(subset=('IndexCode')) 
qq.sort_values(by = 'IndexCode' ,ascending=True,ignore_index=True)\
               .set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/tdxIndexsCode.xlsx')
print('=========> Indexs OK ')