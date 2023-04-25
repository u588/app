from sqlalchemy import create_engine
import requests
import random
import json
import pandas as pd

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36 Edg/98.0.1108.43'}
cookie = {'acw_sc__v3':''}


cookie['acw_sc__v3'] = '642b80175844102decf1f94b9761fc757345fd95'


startDate = '20230329'
endDate = '20230403'
tDate = '2023-04-03'



eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

def getData(codeID):
    url = 'https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode='+codeID+'&startDate='+startDate+'&endDate='+endDate
    data = requests.get(url, headers=header,cookies=cookie)
    Ddata = json.loads(data.text)['data']
    pdData = pd.DataFrame(Ddata)[['tradeDate', 'indexCode', 'indexNameCn','open','high','low', 'close', 'change', 'changePct', 'tradingVol', 'tradingValue']]
    a = pdData
    a.columns=['Date','Index_code', 'Index_name','Open','High','Low','Close','Change','PCB','Vol','Tum']
    a.Date = a['Date'].str[:4] +'-' +a['Date'].str[4:6] +'-'+ a['Date'].str[6:]
    a.Tum = a.Tum*100000000
    a.Vol = a.Vol*100000000
    a.set_index('Date',inplace=True)
    a.sort_index(inplace=True)
    return a

IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()
random.shuffle(IndexLists)

for codeID in IndexLists:
    try:
        DayUp = tDate
        Day = pd.read_sql(codeID, eng).tail(1)['Date'].to_list()[0]
        if DayUp > Day:
            try:
                Data = getData(codeID)
                Data.to_sql(codeID, eng , if_exists='append')
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