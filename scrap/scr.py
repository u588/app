# 导入库
import time
import json
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup

# 获取单页数据
def get_html(page_id):
  headers={
      'Host':'q.10jqka.com.cn',
      'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',
      'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Language':'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
      'Accept-Encoding':'gzip, deflate',
      'Connection':'keep-alive',
      'Cookie':'v=Ap3l5Y1Cn_putnvW5Hlqy1VFrHiWutEM2-414F9i2fQjFrPqJwrh3Gs-RHbs; searchGuide=sg; historystock=688598%7C*%7C000001%7C*%7C600000%7C*%7C600196; Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1590039549; Hm_lpvt_78c58f01938e4d85eaf619eae71b4ed1=1590041303; spversion=20130314',
      'Upgrade-Insecure-Requests': '1'
    }
  url = 'http://q.10jqka.com.cn/index/index/board/all/field/zdf/order/desc/page/'+str(page_id)+'/ajax/1/'
  res = requests.get(url,headers=headers)
  res.encoding = 'GBK'
  soup = BeautifulSoup(res.text,'lxml')
  tr_list = soup.select('tbody tr')
  # print(tr_list)
  stocks = []
  for each_tr in tr_list:
    td_list = each_tr.select('td')
    data = {
    '股票代码':td_list[1].text,
    '股票简称':td_list[2].text,
    '股票链接':each_tr.a['href'],
    '现价':td_list[3].text,
    '涨幅':td_list[4].text,
    '涨跌':td_list[5].text,
    '涨速':td_list[6].text,
    '换手':td_list[7].text,
    '量比':td_list[8].text,
    '振幅':td_list[9].text,
    '成交额':td_list[10].text,
    '流通股':td_list[11].text,
    '流通市值':td_list[12].text,
    '市盈率':td_list[13].text,
    }
    stocks.append(data)
  return stocks

# 保存数据
def write2excel(result):
  json_result = json.dumps(result)
  with open('stocks.json','w') as f:
    f.write(json_result)
  with open('stocks.json','r') as f:
    data = f.read()
    data = json.loads(data)
    df = pd.DataFrame(data,columns=['股票代码','股票简称','股票链接','现价','涨幅','涨跌','涨速','换手','量比','振幅','成交额',  '流通股','流通市值','市盈率'])
    df.to_csv('/home/ts/app/scrap/stocks.csv',index=False)

def get_pages(page_n):
  stocks_n = []
  for page_id in range(1,page_n+1):
    page = get_html(page_id)
    stocks_n.extend(page)
    time.sleep(random.randint(1,5))
  return stocks_n

c = get_pages(5)
write2excel(c)