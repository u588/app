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
    item['name'] = r_li[0]
    item['code'] = r_li[1]

    fr = requests.get(fUrl, headers=header)
    fhtml= etree.HTML(fr.content.decode('gbk'))
    fr_li=fhtml.xpath("//div[@id='fieldstatus']//span/text()")[0].split(' -- ')
    item['icLev1'] = fr_li[0]
    item['icLev2'] = fr_li[1]
    item['icLev3'] = fr_li[2].strip(' （共')
   
    dr = requests.get(dUrl, headers=header)
    dhtml = etree.HTML(dr.content)
    dr_li = dhtml.xpath("//table[@class='m_table']//span/text()")
    item['fName'] = dr_li[0]
    item['regi'] = dr_li[1]

    m_li = dhtml.xpath("//table[@class='m_table ggintro managelist']/tbody/tr")
    temp = dhtml.xpath("//strong[contains(text(),'控股股东')]")[0].xpath("..//span/text()")
    item['mBiz'] = m_li[0].xpath(".//span/text()")

    item['cSH'] = temp[0].strip() if len(temp)>0 else None
    # item['cSHr'] = re.findall("：(.*?)%", temp[1]) if len(re.findall("：(.*?)%", temp[1]))>0 else None    
    if len(temp)>0:
        if len(re.findall("：(.*?)%", temp[1]))>0:
            item['cSHr'] = re.findall("：(.*?)%", temp[1])
    else:
        item['cSHr'] = None


    item['acSH'] = m_li[2].xpath(".//span/text()")[0].strip() if len(m_li[2].xpath(".//span/text()"))>0 else None
    # item['acSHr'] = re.findall("：(.*?)%", m_li[2].xpath(".//span/text()")[1]) if len(m_li[2].xpath(".//span/text()"))>0 else None
    if len(m_li[2].xpath(".//span/text()"))>0:
        if len(re.findall("：(.*?)%", m_li[2].xpath(".//span/text()")[1]))>0:
            item['acSHr'] = re.findall("：(.*?)%", m_li[2].xpath(".//span/text()")[1])
    else:
        item['acSHr'] = None 

    item['ucSH'] = m_li[3].xpath(".//span/text()")[0].strip() if len(m_li[3].xpath(".//span/text()"))>0 else None
    # item['ucSHr'] = re.findall("：(.*?)%", m_li[3].xpath(".//span/text()")[1]) if len(m_li[3].xpath(".//span/text()"))>0 else None
    if len(m_li[3].xpath(".//span/text()"))>0:
        if len(re.findall("：(.*?)%", m_li[3].xpath(".//span/text()")[1]))>0:
            item['ucSHr'] = re.findall("：(.*?)%", m_li[3].xpath(".//span/text()")[1])
    else:
        item['ucSHr'] = None 
    
    try:
        item['regCap'] = m_li[-4].xpath(".//span/text()")[-2].strip()
    except:
        item['regCap'] = None

    try:
        item['empNum'] = m_li[-4].xpath(".//span/text()")[-1].strip()
    except:
        item['empNum'] = None
    try:
        item['addr'] = m_li[-2].xpath(".//span/text()")[0].strip()
    except:
        item['addr'] = None
    # print(item)
    data = pd.DataFrame(item)
    data.set_index('code', inplace=True)
    return data

def getManag(stockID):

    dUrl = 'http://basic.10jqka.com.cn/'+stockID+'/company.html#stockpage'
    Data = pd.DataFrame()
    item = {}

    dr = requests.get(dUrl, headers=header)
    dhtml = etree.HTML(dr.content)
    ml_li = dhtml.xpath("//table[@class='m_table managelist m_hl']")

    for i in ml_li:
        tr_li = i.xpath("./tbody/tr")

        for l in tr_li:
            item['mName'] = l.xpath("./td[@class='tc name']/a/text()")
            item['postion'] = l.xpath("./td[@class='tl']/text()")

            mdate = l.xpath("./td/div/span/text()")
            if len(mdate)>3:
                item['dShare'] = mdate[:4:2]
                item['iShare'] = mdate[1:4:2]
            else:
                item['dShare'] = mdate[0]
                item['iShare'] = mdate[1]
            item['intro'] = l.xpath(".//p/text()")[:4:2]
            # print(item)
            data = pd.DataFrame.from_dict(item, orient='columns')
            Data = Data.append(data, ignore_index=True)
            Data['code'] = stockID
            Data.set_index('code', inplace=True)
    return Data

def getAff(stockID):

    dUrl = 'http://basic.10jqka.com.cn/'+stockID+'/company.html#stockpage'
    Data = pd.DataFrame()
    amData = pd.DataFrame()
    item = {}

    dr = requests.get(dUrl, headers=header)
    dhtml = etree.HTML(dr.content)

    aff_li = dhtml.xpath("//table[@class='m_table m_hl ggintro business']//tbody/tr")

    for i in aff_li:
        item['cName'] = i.xpath(".//p/text()")
        try:
            durl = "http://basic.10jqka.com.cn/ajax/stock/company.php?id="+i.xpath(".//p/@orgid")[0]
            tt = json.loads(requests.get(durl, headers=header).text)['data']
            time.sleep(random.randint(1,2))
            item['cEst']=tt['info']['date']
            item['cCap']=tt['info']['money']
            item['cLeg']=tt['info']['person']
            teData = pd.DataFrame(tt['manager'])[['name', 'job']].rename(columns={'name':'mName','job':'postion'})
            teData['cName'] = tt['info']['name']
            tempDate = i.xpath(".//td/text()")
            item['cRel'] = tempDate[4]
            item['cRat'] = tempDate[5]
            item['iCap'] = tempDate[6]
            item['cPro'] = tempDate[7]
            item['mRep'] = tempDate[8]
            item['cBiz'] = tempDate[9].strip()
            data = pd.DataFrame(item,index=[0])
            Data = Data.append(data, ignore_index=True)
            amData = amData.append(teData, ignore_index=True)
        except:
            tempDate = i.xpath(".//td/text()")
            item['cRel'] = tempDate[4]
            item['cRat'] = tempDate[5]
            item['iCap'] = tempDate[6]
            item['cPro'] = tempDate[7]
            item['mRep'] = tempDate[8]
            item['cBiz'] = tempDate[9].strip()
            item['cLeg'] = None
            item['cCap'] = None
            item['cEst'] = None
            data = pd.DataFrame(item,index=[0])
            Data = Data.append(data, ignore_index=True)           

    Data['code'] = stockID
    Data.set_index('code', inplace=True)
    amData.set_index('cName', inplace=True)
    return Data,amData