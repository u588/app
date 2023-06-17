import json
import re
import pandas as pd
a = open('G:/Gitee/880-881.json', 'r',encoding="utf-8").read()
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



qq = q.loc[~((q[0]=='999999') & (q[1]=='399001'))].drop_duplicates(subset=[0,1,2,3], keep='first')
qq = qq.loc[~((qq[0]=='399002'))]

qq.reset_index(drop=True, inplace=True)
qq.drop(0, inplace=True)

n = 1
while n <=2710:
    if pd.isna(qq.loc[n][1]):
        qq.loc[n+1,['IndexCode']]= qq.loc[n, [0]][0]
    else:
        pass
    n = n +1 

qq.dropna(thresh=3, inplace=True)
qq.reset_index(drop=True, inplace=True)
qq['IndexCode'] = qq['IndexCode'].fillna(method='ffill')

IndexCons = pd.DataFrame(columns=['IndexCode', 'StockCode'])
Indexs = pd.DataFrame(columns=['IndexCode', 'Num'])
c = pd.Series()
n=0
IndexCode='880082'
while n < 1676:
    while IndexCode == qq.loc[n]['IndexCode']:
        x = qq.loc[n].dropna()
        c = pd.concat([c,x])
        n = n + 1
    c.drop_duplicates(inplace=True)
    c.drop(0, inplace=True)
    c.reset_index(drop=True, inplace=True)
    l = [IndexCode,len(c)]
    dfl = pd.DataFrame(l).T
    dfl.columns = ['IndexCode', 'Num']
    Indexs = pd.concat([Indexs, dfl], ignore_index=True)
    dfc = pd.DataFrame(c)
    dfc.columns = ['StockCode']
    dfc['IndexCode'] = IndexCode
    IndexCons = pd.concat([IndexCons, dfc], ignore_index=True)
    IndexCode = qq.loc[n]['IndexCode']
    c = pd.Series()
    print(str(n)+ "  ok !")



