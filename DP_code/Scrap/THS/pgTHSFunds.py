import requests
# import re
from lxml import etree
# import json
from sqlalchemy import create_engine
import pandas as pd
# import datetime
import time
import random

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')
StockLists = pd.read_sql('StocksList', engs).code.tolist()

def getFunds(stockID):
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
    url = 'http://stockpage.10jqka.com.cn/'+stockID+'/funds/'

    r = requests.get(url, headers=header)
    html= etree.HTML(r.content.decode())

    his_table=html.xpath("//div[@id='history_table_free']")[0]

    funds_li=his_table.xpath(".//tr[@class='' or @class='even']")
    Data = pd.DataFrame()
    i = funds_li[0]
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
    data.set_index('date', inplace=True)
    return data

for stockID in StockLists:
    try:
        Data = getFunds(stockID)
        DayUp = Data.reset_index()['date'].to_list()[0]
        Day = pd.read_sql(stockID,eng).tail(1)['date'].to_list()[0]
        time.sleep(random.randint(1,3))
        # if stockID >'002669':

        if DayUp > Day:
            Data.to_sql(stockID, eng , if_exists='append')
            
            print(stockID + 'Updated !')
        else:
            print('Not Save! '+stockID)
            pass        

    except:
        Data.to_sql(stockID, eng , if_exists='append')
        
        pass
print('All saved !')