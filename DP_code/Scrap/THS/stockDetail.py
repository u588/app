import requests
import re
from lxml import etree
import pandas as pd
import json
import time
import random

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
header1 = {"User-Agent": "Mozilla/5.0 (Linux; Android 7.0; SM-G892A Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36",}


def getDetail(stockID):
    
    # url = 'http://stockpage.10jqka.com.cn/'+stockID+'/company'
    url = 'http://stockpage.10jqka.com.cn/'+stockID+'/'
    fUrl = 'http://basic.10jqka.com.cn/'+stockID+'/field.html#stockpage'
    dUrl = 'http://basic.10jqka.com.cn/'+stockID+'/company.html#stockpage'

    item = {}

    r = requests.get(url, headers=header)
    html= etree.HTML(r.content)
    r_li=html.xpath("//div[@id='in_squote']//strong/text()")
    item['StockName'] = r_li[0]
    item['StockCode'] = r_li[1]

    fr = requests.get(fUrl, headers=header)
    fhtml= etree.HTML(fr.content.decode('gbk'))
    fr_li=fhtml.xpath("//div[@id='fieldstatus']//span/text()")[0].split(' -- ')
    item['L1Name'] = fr_li[0]
    item['L2Name'] = fr_li[1]
    item['L3Name'] = fr_li[2].strip(' （共')
   
    dr = requests.get(dUrl, headers=header)
    dhtml = etree.HTML(dr.content)
    dr_li = dhtml.xpath("//table[@class='m_table']//span/text()")
    item['公司名称'] = dr_li[0]
    item['所属地域'] = dr_li[1]

    m_li = dhtml.xpath("//table[@class='m_table ggintro managelist']/tbody/tr")
    temp = dhtml.xpath("//strong[contains(text(),'控股股东')]")[0].xpath("..//span/text()")
    item['主营业务'] = m_li[0].xpath(".//span/text()")

    item['控股股东'] = temp[0].strip() if len(temp)>0 else None
    # item['cSHr'] = re.findall("：(.*?)%", temp[1]) if len(re.findall("：(.*?)%", temp[1]))>0 else None    
    if len(temp)>0:
        if len(re.findall("：(.*?)%", temp[1]))>0:
            item['控股率'] = re.findall("：(.*?)%", temp[1])
    else:
        item['控股率'] = None


    item['实际控制人'] = m_li[2].xpath(".//span/text()")[0].strip() if len(m_li[2].xpath(".//span/text()"))>0 else None
    # item['acSHr'] = re.findall("：(.*?)%", m_li[2].xpath(".//span/text()")[1]) if len(m_li[2].xpath(".//span/text()"))>0 else None
    if len(m_li[2].xpath(".//span/text()"))>0:
        if len(re.findall("：(.*?)%", m_li[2].xpath(".//span/text()")[1]))>0:
            item['实控率'] = re.findall("：(.*?)%", m_li[2].xpath(".//span/text()")[1])
    else:
        item['实控率'] = None 

    item['最终控制人'] = m_li[3].xpath(".//span/text()")[0].strip() if len(m_li[3].xpath(".//span/text()"))>0 else None
    # item['ucSHr'] = re.findall("：(.*?)%", m_li[3].xpath(".//span/text()")[1]) if len(m_li[3].xpath(".//span/text()"))>0 else None
    if len(m_li[3].xpath(".//span/text()"))>0:
        if len(re.findall("：(.*?)%", m_li[3].xpath(".//span/text()")[1]))>0:
            item['终控率'] = re.findall("：(.*?)%", m_li[3].xpath(".//span/text()")[1])
    else:
        item['终控率'] = None 
    
    try:
        item['注册资金'] = m_li[-4].xpath(".//span/text()")[-2].strip()
    except:
        item['注册资金'] = None

    try:
        item['员工人数'] = m_li[-4].xpath(".//span/text()")[-1].strip()
    except:
        item['员工人数'] = None
    try:
        item['办公地址'] = m_li[-2].xpath(".//span/text()")[0].strip()
    except:
        item['办公地址'] = None
    # print(item)
    data = pd.DataFrame(item)
    data.set_index('StockCode', inplace=True)
    return data
