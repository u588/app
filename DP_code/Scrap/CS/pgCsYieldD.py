from sqlalchemy import create_engine
import requests
from lxml import etree
import pandas as pd
import random
import json
import time

#header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.67',}
eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')

def getData(codeID):
    
    url = "https://www.csindex.com.cn/csindex-home/perf/get-index-yield-item/"+codeID
    data = requests.get(url, headers=header)
    Ddata = json.loads(data.text)['data']
    pdData = pd.DataFrame(Ddata, index=[0])[['indexCode', 'indexNameCn','endDate','oneMonth','threeMonth','thisYear', 'oneYear', 'threeYear', 'fiveYear']]
    a = pdData
    a.columns=['IndexCode', 'IndexName','Date','Yie1M','Yie3M','YieToNow', 'Yie1Y','Yie3Y', 'Yie5Y']
    a.set_index('IndexCode',inplace=True)
    return a

IndexLists = pd.read_sql('tdxIndexs', eng).IndexCode.to_list()
random.shuffle(IndexLists)
D = pd.DataFrame(columns=['IndexCode', 'IndexName','Date','Yie1M','Yie3M','YieToNow', 'Yie1Y','Yie3Y', 'Yie5Y'])
D.set_index('IndexCode', inplace=True)


for codeID in IndexLists:
    try:
        Da = getData(codeID)
        
        time.sleep(random.randint(0,2))
        D =pd.concat([D, Da])
        print(codeID + 'Saved !')
    except:
        print('Not Save!'+ codeID)  
        pass
D.dropna(inplace=True)
D.set_index('IndexCode').to_sql('csYield', eng , if_exists='replace')
print(' == 指数收益率 All Saved ! == ')    

