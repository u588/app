from sqlalchemy import create_engine
import requests
import pandas as pd
import random
import time

#header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.67',}
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')


# sql = 'DROP TABLE IF EXISTS "csIndexCons";'
eng.execute('DROP TABLE IF EXISTS "csIndexCons";')
time.sleep(5)

def getData(codeID):
    # url = "http://www.csindex.com.cn/zh-CN/indices/index-detail/"+codeID
    # url = "https://csi-web-dev.oss-cn-shanghai-finance-1-pub.aliyuncs.com/static/html/csindex/public/uploads/file/autofile/closeweight/"+codeID[0]+"closeweight.xls"
    url = 'https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/closeweight/' +codeID[0] +'closeweight.xls'

    r = requests.get(url, headers=header)
    # html= etree.HTML(r.content)
    # urlD = html.xpath("//ul[@class='download clearfix mb-10']//li/a[contains(text(),'成份列表')]")[0].xpath("@href")[0]
    # r = requests.get(urlD, headers=header)
    a = pd.read_excel(r.content,index_col=None, header=None,skiprows=1,dtype={1:object,4:object})[[1,2,4,5,9]]
    # a.columns=['IndexCode', 'IndexName','StockCode','StockName', 'Weight']
    a.columns=['IndexCode', 'IndexName','StockCode','StockName', 'IndexSTL']
    a.IndexSTL = codeID[1]
    a.set_index('IndexCode',inplace=True)
    return a

# IndexLists = pd.read_sql('csCIndexs', eng).IndexCode.to_list()
ls = pd.read_sql('tdxIndexs', eng)
dd = ls[ls.From=='CS'][['IndexCode','IndexSTL']]
IndexLists = dd.apply(lambda row: row.tolist(), axis=1).tolist()
random.shuffle(IndexLists)

for codeID in IndexLists:
    try:
        Data = getData(codeID)
        time.sleep(random.randint(1,3))
        Data.to_sql('csIndexCons', eng , if_exists='append')

        # print(codeID[0] + 'Saved !')
    except:
        print('Not Save!  '+ codeID[0])
        pass
print(' == 指数成份股 All Saved ! == ')