import re
import pandas as pd

sh = open('D:/new_tdx/T0002/hq_cache/shm.tnf', 'r',encoding="GBK", errors='ignore').read()
sz = open('D:/new_tdx/T0002/hq_cache/szm.tnf', 'r',encoding="GBK", errors='ignore').read()


shIndex00 = re.findall(r"00\d{4}.{30}", sh)
shIndex88 = re.findall(r"88\d{4}.{30}", sh)
szIndex39 = re.findall(r"39\d{4}.{30}", sz)

DataIndex = [shIndex00, shIndex88]
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
qq['Market'] = 'ST'
qq['MarketName'] = 'SH'
qq['MarketCode'] = '1'
qq['From'] = 'TDX'
# qq['IndexSTL'] = '指数'
qq.sort_values(by = 'IndexCode' ,ascending=True,ignore_index=True)\
               .set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxSHIndexs.xlsx')
print('=========> Indexs OK ')


DataIndex = [szIndex39]
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
qq['Market'] = 'ST'
qq['MarketName'] = 'SZ'
qq['MarketCode'] = '0'
qq['From'] = 'TDX'
# qq['IndexSTL'] = '指数'
qq.sort_values(by = 'IndexCode' ,ascending=True,ignore_index=True)\
               .set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/tdxSZIndexs.xlsx')
print('=========> Indexs OK ')