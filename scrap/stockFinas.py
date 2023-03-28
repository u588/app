import requests
import re
from lxml import etree
import pandas as pd
import json

from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
display = Display(visible=0, size=(900, 800))
display.start()
driver = webdriver.Firefox()


def getFunds(stockID):
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',}
    url = 'http://stockpage.10jqka.com.cn/'+stockID+'/finance/'

    r = requests.get(url, headers=header)
    html= etree.HTML(r.content.decode())

    his_table=html.xpath("//div[@id='history_table_free']")[0]

    funds_li=his_table.xpath(".//tr[@class='' or @class='even']")
    Data = pd.DataFrame()
    for i in funds_li :
        item = {}
        item['date'] = pd.to_datetime(i.xpath("./td/text()")[0]).strftime('%Y-%m-%d')
        item['close'] = i.xpath("./td/text()")[1]
        item['chg'] = i.xpath("./td/text()")[2]
        item['inflow'] = i.xpath("./td/text()")[3]
        item['5dbEqu'] = i.xpath("./td/text()")[4]
        item['bEqu'] = i.xpath("./td/text()")[5]
        item['bShare'] = i.xpath("./td/text()")[6]
        item['mEqu'] = i.xpath("./td/text()")[7]
        item['mShare'] = i.xpath("./td/text()")[8]
        item['sEqu'] = i.xpath("./td/text()")[9]
        item['sShare'] = i.xpath("./td/text()")[10]
        data = pd.DataFrame(item,index=[0])
        # print(data)
        Data = Data.append(data, ignore_index=True)
    # Data.to_csv('./data4.csv')   
    Data.sort_values('date', inplace=True, ascending=True)
    Data.set_index('date', inplace=True)
    return Data