import numpy as np
import pandas as pd
from sqlalchemy import create_engine

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/FindStocks')


def getDate():
    data = pd.read_sql('FindStocks', eng).sort_values(by=['datetime'], ascending=False)
    data = data.drop_duplicates(subset=('datetime'), keep='first').reset_index()
    d = data[['datetime','code']].to_json(orient='records')
    return d

def getCode(date):
    data = pd.read_sql('FindStocks', eng).sort_values(by=['datetime'], ascending=False)
    data = data.drop_duplicates(subset=(['datetime','code']), keep='first').reset_index()
    d = data[['datetime','code']].groupby('datetime').get_group(date).sort_values(by='code').to_json(orient='records')
    return d

