from sqlalchemy import create_engine
import requests

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
    urlD = html.xpath("//ul[@class='download clearfix mb-10']//li/a[contains(text(),'指数行情')]")[0].xpath("@href")[0]
    r = requests.get(urlD, headers=header)
    a = pd.read_excel(r.content,index_col=None, header=None,skiprows=1,dtype={1:object})[[0,1,3,6,7,8,9,10,11,12,13]].dropna(subset=[9])
    a.columns=['Date','Index_code', 'Index_name','Open','High','Low','Close','Change','PCB','Vol','Tum']
    a.set_index('Date',inplace=True)
    a.sort_index(inplace=True)
    return a

IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()

for codeID in IndexLists:
    try:
        Data = getData(codeID).tail(1)
        DayUp = Data.reset_index().tail(1)['Date'].to_list()[0]
        Day = pd.read_sql(codeID, eng).tail(1)['Date'].to_list()[0]

        if DayUp > Day:
            Data.to_sql(codeID, eng , if_exists='append')
            time.sleep(random.randint(1,3))
            print(codeID + 'Updated !')
        else:
            pass
    except:
        print('Not Updated ! '+ codeID)
        pass
print(' == 指数行情 All Updated ! == ')