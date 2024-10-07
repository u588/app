from mootdx.quotes import Quotes
import pandas as pd
import re
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/StockBas')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxStocks')

def getTop(StockCode, StockName):
    qf10='热点题材'
    client = Quotes.factory(market='std')
    txtRaw = client.F10(StockCode, qf10)[116:]

    txt = txtRaw.replace('│',' ')                
    txt = re.sub('([\u2500-\u25f7])','',txt)
    
    # txt = re.findall(r'│(.*)│(关联度.*☆{4,})',txt)
    txt = re.findall(r'(\S+)\s+(\S+)\s+关联度.*(☆{4,})',txt)
    txDF = pd.DataFrame(txt)
    # txDF = txDF.map(lambda x: x.rstrip() if isinstance(x, str) else x)

    txDF[2]=txDF[2].str.len()
    txDF.columns=['日期','题材','相关度']
    txDF['StockCode'] = StockCode
    txDF['StockName'] = StockName
    txDF.set_index('StockCode').to_sql('Top', eng, if_exists='append')


StockList = pd.read_sql('StocksList', engs)[['code','name']]
n = 0
while n < len(StockList):
    try:
        getTop(StockList.iloc[n,0], StockList.iloc[n,1])
        print(StockList.iloc[n,0]+ 'OK !')
        
    except:
        print(StockList.iloc[n,0] + 'Failure ! ')
       
        pass
    n = n + 1