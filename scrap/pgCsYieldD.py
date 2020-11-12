from sqlalchemy import create_engine
import requests
import re
from lxml import etree
import pandas as pd
import random
import time

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

def getData(codeID):
    
    url = "http://www.csindex.com.cn/zh-CN/indices/index-detail/"+codeID
    r = requests.get(url, headers=header)
    html= etree.HTML(r.content)
    urlD = html.xpath("//ul[@class='download clearfix mb-10']//li/a[contains(text(),'收益率')]")[0].xpath("@href")[0]
    r = requests.get(urlD, headers=header)
    a = pd.read_excel(r.content,index_col=None, header=None,skiprows=1, dtype={0:object})
    a.columns=['Index_code', 'Index_name','Date','Yie1M','Yie3M','YieToNow', 'Yie1Y','Yie3Y', 'Yie5Y','2016','2017','2018','2019']
    a.set_index('Index_code',inplace=True)
    return a

IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()

for codeID in IndexLists:
    try:
        Data = getData(codeID).tail(1)
        DayUp = Data.reset_index().tail(1)['Date'].to_list()[0]
        Day = pd.read_sql('csYield', eng)['Date'].to_list()[0]

        if DayUp > Day:        
            getData(codeID).to_sql('csYield', eng , if_exists='append')
            time.sleep(random.randint(1,3))
            print(codeID + 'Saved !')
        else:
            pass
    except:
        print('Not Save!'+ codeID)  
        pass
print(' == 指数收益率 All Saved ! == ')