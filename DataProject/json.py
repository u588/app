import json
import re
import pandas as pd
a = open('G:/Gitee/App/1.json', 'r').read()
data = json.loads(a)
n = len(data)
q = pd.DataFrame
i=0
while i < n:
    try:
        aa = data[i]['_source']['layers']['data']['data.data'].replace(':', '')
        aaa = bytes.fromhex(aa).decode(errors='ignore')
        c = re.findall("\d{6}", aaa)
        c1 = pd.DataFrame(c).T
        q = pd.concat([q,c1])
        i = i+1
        print(str(i) +' concated !')
    except:
        i = i + 1
        pass


