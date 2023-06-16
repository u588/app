import json
import re

a = open('G:/Gitee/App/1.json', 'r').read()
data = json.loads(a)
aa = data[19]['_source']['layers']['data']['data.data'].replace(':', '')

aaa = bytes.fromhex(aa).decode(errors='ignore')
re.findall("\d{6}", aaa)