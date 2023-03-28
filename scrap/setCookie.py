from sqlalchemy import create_engine
import requests
import datetime
import json

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver import ChromeOptions

from lxml import etree
import pandas as pd
import random
import time

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36 Edg/98.0.1108.43'}
option = ChromeOptions()
option.add_experimental_option('excludeSwitches', ['enable-automation'])

option.add_experimental_option('useAutomationExtension', False)





web = webdriver.Remote(command_executor='http://10.3.18.55:11111/wd/hub',options=option)



web.get('https://www.csindex.com.cn')

try:
    submit_btn = web.find_element_by_id('nc_1_n1z')
    ActionChains(web).drag_and_drop_by_offset(submit_btn,xoffset = 300,yoffset = 0).perform()
    time.sleep(3)
except:
    pass

cookie = {'acw_tc':'76b20f6b16434378829243340e0f6bc5d7b409b0484a31f2dbd7916d3f6caf', 'acw_sc__v3':'61f4e67626f2021c441d376449d7380e7ea71202'}
cookie = {'acw_sc__v3':'6203169ed6c36682bb4c7cb368d4e249d851f7d7'}
cookie['acw_sc_v3'] = web.get_cookie("acw_sc_v3")['value']


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

def getData(codeID):
    # tradeDate = datetime.datetime.now().strftime('%Y%m%d')
    # tDate = datetime.datetime.now().strftime('%Y-%m-%d')
    tradeDate = '20220208'
    tDate = '2022-02-08'

  
    url = 'https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode='+codeID+'&startDate='+tradeDate+'&endDate='+tradeDate
 
    data = requests.get(url, headers=header)
    Ddata = json.loads(data.text)['data'][0]
    pdData = pd.DataFrame(Ddata, index=[0])[['tradeDate', 'indexCode', 'indexNameCn','open','high','low', 'close', 'change', 'changePct', 'tradingVol', 'tradingValue']]
    a = pdData
    a.columns=['Date','Index_code', 'Index_name','Open','High','Low','Close','Change','PCB','Vol','Tum']
    a.Date = tDate
    a.Tum = a.Tum*100000000
    a.Vol = a.Vol*100000000
    a.set_index('Date',inplace=True)
    a.sort_index(inplace=True)
    return a

IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()

for codeID in IndexLists:
    try:
        DayUp = '2022-02-08'
        Day = pd.read_sql(codeID, eng).tail(1)['Date'].to_list()[0]
        if DayUp > Day:
            try:
                Data = getData(codeID)
                Data.to_sql(codeID, eng , if_exists='append')
                # time.sleep(random.randint(0,2))
                print(codeID + 'Updated !')
            except:
                print('WWW noData ! '+ codeID)
                pass        
        else:
            print('DataBas noUp'+ codeID)
            pass
    except:
        print('DataBas NoData ! '+ codeID)
        pass 

print(' == 指数行情 All Updated ! == ')