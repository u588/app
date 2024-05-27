# import numpy as np
import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/FindStocks')


def getDate():
    data = pd.read_sql('FindStocks', eng).sort_values(by=['datetime'], ascending=False)
    data = data.drop_duplicates(subset=('datetime'), keep='first').reset_index()
    d = data[['datetime','code']]
    return d

def getCode(date):
    data = pd.read_sql('FindStocks', eng).sort_values(by=['datetime'], ascending=False)
    data = data.drop_duplicates(subset=(['datetime','code']), keep='first').reset_index()
    d = data[['datetime','code']].groupby('datetime').get_group(date).sort_values(by='code')
    return d

