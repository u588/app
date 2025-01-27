from mootdx.quotes import Quotes
import pandas as pd
import re
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/StockBas')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxStocks')



def getFcast(StockCode, StockName):
    qf10='研报评级'
    client = Quotes.factory(market='std')
    txtRaw = client.F10(StockCode, qf10)[116:]

    txt = txtRaw.replace('│',' ')                
    txt = re.sub('([\u2500-\u25f7])','',txt)
    
    ftxt = txt[txt.find('【2.盈利预测统计】'):]
    etxt = ftxt[:ftxt.find('【3.盈利预测明细】')]
    dd = etxt.splitlines(keepends=False)

    Data = pd.DataFrame(columns=())
    i = 0
    while i < len(dd):
        lis = dd[i].split()
        if len(lis)!=7:
            pass
        else:
            df = pd.DataFrame(lis).T
            Data = pd.concat([Data, df],axis=0)
        i=i+1
    Data.reset_index(drop=True,inplace=True)
    Data = Data.replace('---',pd.NA)

    Data.columns=list(Data.loc[0])
    Data['StockCode'] = StockCode
    Data['StockName'] = StockName

    Data[['StockCode','StockName', '财务指标', '2021年', '2022年', '2023年', '2024年预测', '2025年预测','2026年预测' ]].tail(-1).set_index('StockCode').to_sql('Fcast', eng, if_exists='append')


StockList = pd.read_sql('StocksList', engs)[['code','name']]
n = 0
while n < len(StockList):
    try:
        getFcast(StockList.iloc[n,0], StockList.iloc[n,1])
        print(StockList.iloc[n,0]+ 'OK !')
        
    except:
        print(StockList.iloc[n,0] + 'Failure ! ')
       
        pass
    n = n + 1