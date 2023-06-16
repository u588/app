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
