from sqlalchemy import create_engine
import requests
import datetime
import json

from lxml import etree
import pandas as pd
import random
import time

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36 Edg/97.0.1072.69',
          'Cookie':'acw_sc__v3=620321a64530fe602bc4939d312a31d4cc25811a'          
}
eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

def getData(codeID):
    tradeDate = datetime.datetime.now().strftime('%Y%m%d')
    tDate = datetime.datetime.now().strftime('%Y-%m-%d')

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
        Data = getData(codeID)
        DayUp = Data.reset_index()['Date'].to_list()[0]
        # Day = pd.read_sql(codeID, eng).tail(1)['Date'].to_list()[0].strftime('%Y-%m-%d')
        Day = pd.read_sql(codeID, eng).tail(1)['Date'].to_list()[0]

        if DayUp > Day:
            Data.to_sql(codeID, eng , if_exists='append')
            time.sleep(random.randint(0,2))
            print(codeID + 'Updated !')
        else:
            pass
    except:
        print('Not Updated ! '+ codeID)
        pass
print(' == 指数行情 All Updated ! == ')
eng.dispose()