import json
import re
import pandas as pd
a = open('G:/Gitee/tdxAppAutoGui1.json', 'r',encoding="utf-8").read()
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


qq = q.loc[~((q[0]=='999999')|(q[0]=='399002') )]
qq = qq.drop_duplicates(keep='first').reset_index(drop=True).drop(0).reset_index(drop=True)


IndexCons = pd.DataFrame(columns=['IndexCode', 'StockCode'])
Indexs = pd.DataFrame(columns=['IndexCode', 'Num'])
c = pd.Series()
n=1
IndexCode='399234'
while n < qq.shape[0]:
    try:
        while qq.loc[n].dropna().shape[0] >= 2:
            x = qq.loc[n].dropna()
            c = pd.concat([c,x])
            n = n + 1
    except:
        pass
    c.drop_duplicates(inplace=True)
    # c.drop(0, inplace=True)
    c.reset_index(drop=True, inplace=True)
    l = [IndexCode,len(c)]
    dfl = pd.DataFrame(l).T
    dfl.columns = ['IndexCode', 'Num']
    Indexs = pd.concat([Indexs, dfl], ignore_index=True)
    dfc = pd.DataFrame(c)
    dfc.columns = ['StockCode']
    dfc['IndexCode'] = IndexCode
    IndexCons = pd.concat([IndexCons, dfc], ignore_index=True)
    IndexCode = qq.loc[n][0]
    c = pd.Series()
    n = n + 1
    print(str(n)+ "  ok !")

Indexs['From'] = 'TDXGUI'

tdx = pd.read_excel('G:/Gitee/App/tdxAppData/FinalIndexs621.xlsx', dtype={'IndexCode':object})
m1 = pd.merge(tdx, Indexs, on='IndexCode', how='outer')
m1['From'] = m1.From_x.fillna(m1.From_y)
m1['Num'] = m1.Num_x.fillna(m1.Num_y)

m1.set_index('IndexCode').to_excel('g:/gitee/kk.xlsx') 


Indexs.set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/tdxGuiIndex622.xlsx')
IndexCons.set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/tdxGuiIndexCons622.xlsx')