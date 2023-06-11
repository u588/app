import requests
import re
from lxml import etree
import pandas as pd
import json
import time
import random

header1 = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
header = {"User-Agent": "Mozilla/5.0 (Linux; Android 7.0; SM-G892A Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36",}

def getHolder(stockID):

    # url = 'http://stockpage.10jqka.com.cn/'+stockID+'/holder'
    hUrl = 'http://basic.10jqka.com.cn/'+stockID+'/holder.html#stockpage'
    # pUrl = 'http://basic.10jqka.com.cn/'+stockID+'/position.html#stockpage'

    Data = pd.DataFrame()
    item = {}

    hr = requests.get(hUrl, headers=header)
    dhtml = etree.HTML(hr.content.decode('gbk'))
    hdate = dhtml.xpath("//div[@id='bd_list1']/div/div/ul/li/a/text()")
    h_li = dhtml.xpath("//div[@id='bd_list1']//table[@class='m_table m_hl ggintro']")
    cont=0

    for i in h_li:
        tr_li = i.xpath("./tbody/tr")
        item['date'] = hdate[cont]
        cont = cont+1


        for l in tr_li:
            item['hName'] = l.xpath("./th[@class='tl holder_th']/a/text()")[0].strip()
  
            a = l.xpath(".//td/text()")
            b = l.xpath(".//span/text()")
            item['hShare'] = a[0]
            
            item['shareT'] = a[-1]
            if len(b)>1:
                item['ratio'] = a[4]
                item['shareC'] = b[0]
                item['shareR'] = b[1]
            else:
                item['ratio'] = a[3]
                item['shareC'] = '不变'
                item['shareR'] = '不变'
            # print(item)
            data = pd.DataFrame(item, index=[0])
            # Data = Data.append(data, ignore_index=True)
            Data = pd.concat([Data,data], ignore_index=True)
            Data['code'] = stockID
            Data.set_index('code', inplace=True)
    return Data

def getOrgHolder(stockID):
    
    # hUrl = 'http://basic.10jqka.com.cn/'+stockID+'/holder.html#stockpage'
    pUrl = 'http://basic.10jqka.com.cn/'+stockID+'/position.html#stockpage'

    Data = pd.DataFrame()
    item = {}

    hr = requests.get(pUrl, headers=header)
    dhtml = etree.HTML(hr.content.decode('gbk'))
    hdate = dhtml.xpath("//div[@id='holdetail']/div/div/ul/li/a/text()")
    h_li = dhtml.xpath("//div[@id='holdetail']//table[@class='m_table m_hl ggintro organData']")
    cont=0

    for i in h_li:
        tr_li = i.xpath("./tbody/tr")
        item['date'] = hdate[cont]
        cont = cont+1


        for l in tr_li:
            item['hName'] = l.xpath("./th[@class='tl']/span/text()")[0].strip()
  
            a = l.xpath(".//td/text()")
            b = l.xpath(".//span/text()")
            item['orgT'] = a[0]
            item['hShare'] = a[1]
            item['ratio'] = a[3]
            
            if len(b)<2:
                item['shareR'] = a[5].strip()
            else:
                item['shareR'] = b[-1]
            # print(item)
            data = pd.DataFrame(item, index=[0])
            # Data = Data.append(data, ignore_index=True)
            Data = pd.concat([Data,data], ignore_index=True)
            Data['code'] = stockID
            Data.set_index('code', inplace=True)
    return Data

def getStockHolders(stockID):
    OrgHolder = getOrgHolder(stockID)
    Holder = getHolder(stockID)
    data = pd.concat([OrgHolder,Holder]).drop_duplicates(subset=['date','hName'], keep='first')
    data.sort_values('date', inplace=True, ascending=True)
    return data