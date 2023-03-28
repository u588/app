import requests
from sqlalchemy import create_engine
import datetime
import numpy as np
import json
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/smDaily')
#header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.67',}

# def getFina(stockID):
tDate = datetime.datetime.now().strftime('%Y-%m-%d')
url = 'https://www.csindex.com.cn/csindex-home/data-service/sector-change'
data = requests.get(url, headers=header)
Ddata = json.loads(data.text)

Strong = pd.DataFrame(columns = ['code', 'pct_chg','exchange'])
a = pd.DataFrame(Ddata['data']['sectorChangeMapList']['szse_up'])[['sector','changePct']].applymap(lambda x: x.replace('%', ''))
a.columns= ['code', 'pct_chg']
Strong.code = a.code
Strong.pct_chg= a.pct_chg.astype(float)
Strong['date'] = tDate
Strong.exchange = 'sz'
Strong.set_index('date').to_sql('Strong',eng,if_exists='append')

Strong = pd.DataFrame(columns = ['code', 'pct_chg','exchange'])
a = pd.DataFrame(Ddata['data']['sectorChangeMapList']['sse_up'])[['sector','changePct']].applymap(lambda x: x.replace('%', ''))
a.columns= ['code', 'pct_chg']
Strong.code = a.code
Strong.pct_chg= a.pct_chg.astype(float)
Strong['date'] = tDate
Strong.exchange = 'sh'
Strong.set_index('date').to_sql('Strong',eng,if_exists='append')


weak = pd.DataFrame(columns = ['code', 'pct_chg','exchange'])
a = pd.DataFrame(Ddata['data']['sectorChangeMapList']['sse_down'])[['sector','changePct']].applymap(lambda x: x.replace('%', ''))
a.columns= ['code', 'pct_chg']
weak.code = a.code
weak.pct_chg= a.pct_chg.astype(float)
weak['date'] = tDate
weak.exchange = 'sh'
weak.set_index('date').to_sql('weak',eng,if_exists='append')

weak = pd.DataFrame(columns = ['code', 'pct_chg','exchange'])
a = pd.DataFrame(Ddata['data']['sectorChangeMapList']['szse_down'])[['sector','changePct']].applymap(lambda x: x.replace('%', ''))
a.columns= ['code', 'pct_chg']
weak.code = a.code
weak.pct_chg= a.pct_chg.astype(float)
weak['date'] = tDate
weak.exchange = 'sz'
weak.set_index('date').to_sql('weak',eng,if_exists='append')