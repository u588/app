from sqlalchemy import create_engine
import requests
import re
from lxml import etree
import pandas as pd
import random
import time

#header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.67',}
eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

sql = 'DROP TABLE IF EXISTS "csIndexCon";'
eng.execute(sql)

def getData(codeID):
    
    # url = "http://www.csindex.com.cn/zh-CN/indices/index-detail/"+codeID
    url = "https://csi-web-dev.oss-cn-shanghai-finance-1-pub.aliyuncs.com/static/html/csindex/public/uploads/file/autofile/closeweight/"+codeID+"closeweight.xls"
    r = requests.get(url, headers=header)
    # html= etree.HTML(r.content)
    # urlD = html.xpath("//ul[@class='download clearfix mb-10']//li/a[contains(text(),'成份列表')]")[0].xpath("@href")[0]
    # r = requests.get(urlD, headers=header)
    a = pd.read_excel(r.content,index_col=None, header=None,skiprows=1,dtype={1:object,4:object})[[1,2,4,5,9]]
    a.columns=['Index_code', 'Index_name','code','name', 'weight']
    a.set_index('Index_code',inplace=True)
    return a

IndexLists = ['000002']

for codeID in IndexLists:
    try:
        getData(codeID).to_sql('csIndexCon', eng , if_exists='append')
        time.sleep(random.randint(1,3))
        # print(codeID + 'Saved !')
    except:
        print('Not Save!'+ codeID)
        pass
print(' == 指数成份股 All Saved ! == ')