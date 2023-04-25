import requests
import re
from lxml import etree
import pandas as pd
import json

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',}
Data = pd.DataFrame()
def getGK(url):
    url = 'https://gaokao.chsi.com.cn/sch/search.do?searchType=1&zgsx=ylxx&start='+str(url)
    Data = pd.DataFrame()
    r = requests.get(url, headers=header)
    html= etree.HTML(r.content.decode())

    his_table=html.xpath("//table[@class='ch-table']")[0]

    funds_li=his_table.xpath(".//tr")

    for i in funds_li:
        item = {}
        item['name'] = i.xpath(".//text()")[2].strip()
        item['loc'] = i.xpath(".//text()")[5].strip()
        item['manag'] = i.xpath(".//text()")[7].strip()
        item['type'] = i.xpath(".//text()")[9].strip()
        item['edu'] = i.xpath(".//text()")[11].strip()
        try:
            item['mark'] = i.xpath(".//text()")[-3].strip()
        except: 
            item['mark'] = '0'

        data = pd.DataFrame(item,index=[0])
        # print(data)
        Data = Data.append(data, ignore_index=True)
    return Data
for i in range(3):
    j = i*20
    Data = Data.append(getGK(j),ignore_index=True)

# Data.to_csv('./data4.csv')   
Data.sort_values('name', inplace=True, ascending=True)
Data.set_index('name', inplace=True)
Data.to_excel('/home/ts/app/l1gx.xls')