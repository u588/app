from pyecharts.components import Table
from pyecharts.options import ComponentTitleOpts

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/FindStocks')
data = pd.read_sql('FindStocks', eng).sort_values(by=['datetime'], ascending=False)
eng.dispose()
data = data.drop_duplicates(subset=['datetime', 'code'], keep='first')

def filter(a,b):
    data = data[(data.datetime>a) & (data.datetime<b)]
    d = data.groupby(['code','name']).size()
    return d


def table():
    table = Table(js_host='/',page_title='DARK'  )

    headers = data.columns.tolist()
    rows = np.array(data).tolist()
    table.add(headers, rows)
    table.set_global_opts(
        title_opts=ComponentTitleOpts(title="Table-基本示例", subtitle='共有 '+str(data.shape[0]))
    )
    return table
