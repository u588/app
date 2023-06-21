import json
import re
import pandas as pd
a = open('G:/Gitee/tdxAppAutoGui.json', 'r',encoding="utf-8").read()
data = json.loads(a)
n = len(data)
q = pd.DataFrame(['a','b','b']).T

i=0
while i < n:
    try:
        aa = data[i]['_source']['layers']['data']['data.data'].replace(':', '')
        aaa = bytes.fromhex(aa).decode(errors='ignore')
        # c = re.findall("\d{6}", aaa)[::-1]
        c = re.findall("\d{6}", aaa)
        c1 = pd.DataFrame(c).T
        q = pd.concat([q,c1])
        i = i+1
        print(str(i) +' concated !')
    except:
        i = i + 1
        pass
qq = q.loc[~((q[0]=='999999') & (q[1]=='399001'))]

qq = qq.drop_duplicates(subset=[0, 1, 2, 3,4],  keep='first').reset_index(drop=True).drop(0).dropna(thresh=2).reset_index(drop=True)

IndexCons = pd.DataFrame(columns=['IndexCode', 'StockCode'])
Indexs = pd.DataFrame(columns=['IndexCode', 'Num'])
IndexCode = '881004'
c = pd.Series()
n = 0
while n < qq.shape[0]:
    if qq.loc[n][3] == '999999':
        c.drop_duplicates(inplace=True)
        c.reset_index(drop=True, inplace=True)
        l = [IndexCode,len(c)]
        dfl = pd.DataFrame(l).T
        dfl.columns = ['IndexCode', 'Num']
        Indexs = pd.concat([Indexs, dfl], ignore_index=True)
        dfc = pd.DataFrame(c)
        dfc.columns = ['StockCode']
        dfc['IndexCode'] = IndexCode
        IndexCons = pd.concat([IndexCons, dfc], ignore_index=True)
        c = pd.Series()        
        IndexCode = qq.loc[n][0]
    else:
        x = qq.loc[n].dropna()
        c = pd.concat([c,x])
    n = n + 1

















# qq = q.loc[~((q[0]=='999999') & (q[1]=='399001'))]
# qq.drop_duplicates(subset=[0, 1, 2, 3,4],  keep='first', inplace=True)


# qq = qq.loc[~((qq[0]=='399002'))]

# qq.reset_index(drop=True, inplace=True)
# qq.drop(0, inplace=True)

# n = 1
# while n <=2790:
#     if pd.isna(qq.loc[n][1]):
#         qq.loc[n+1,['IndexCode']]= qq.loc[n, [0]][0]
#     else:
#         pass
#     print(str(n)+ ' ok !')
#     n = n +1 

# qq.dropna(thresh=3, inplace=True)
# qq.reset_index(drop=True, inplace=True)
# qq['IndexCode'] = qq['IndexCode'].fillna(method='ffill')

# IndexCons = pd.DataFrame(columns=['IndexCode', 'StockCode'])
# Indexs = pd.DataFrame(columns=['IndexCode', 'Num'])
# c = pd.Series()
# n=0
# IndexCode='395004'
# while n < 1379:
#     while IndexCode == qq.loc[n]['IndexCode']:
#         x = qq.loc[n].dropna()
#         c = pd.concat([c,x])
#         n = n + 1
#     c.drop_duplicates(inplace=True)
#     c.drop(0, inplace=True)
#     c.reset_index(drop=True, inplace=True)
#     l = [IndexCode,len(c)]
#     dfl = pd.DataFrame(l).T
#     dfl.columns = ['IndexCode', 'Num']
#     Indexs = pd.concat([Indexs, dfl], ignore_index=True)
#     dfc = pd.DataFrame(c)
#     dfc.columns = ['StockCode']
#     dfc['IndexCode'] = IndexCode
#     IndexCons = pd.concat([IndexCons, dfc], ignore_index=True)
#     IndexCode = qq.loc[n]['IndexCode']
#     c = pd.Series()
#     print(str(n)+ "  ok !")



