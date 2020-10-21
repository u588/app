from sqlalchemy import create_engine
import pandas as pd
import numpy as np
from pyecharts.components import Table
from pyecharts.options import ComponentTitleOpts


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndexs')

def tablel(Stock):
    IndexConst = pd.read_sql('IndexConst', eng)
    StockInIndex = IndexConst[IndexConst.code==Stock][['index_code', 'code','name']]
    StockInIndex.rename(columns={'name':'stock_name','code':'stock_code'}, inplace=True)
    csIndex = pd.read_sql('IndexList', eng)
    csIndex =csIndex[['index_code', 'index_name']]
    # csIndex.rename(columns={'name':'index_name'}, inplace=True)
    data = pd.merge(StockInIndex, csIndex, on='index_code')  

    tablel = Table(js_host='/',page_title='DARK'  )
    headers = data.columns.tolist()
    rows = np.array(data).tolist()
    tablel.add(headers, rows)
    tablel.set_global_opts(
        title_opts=ComponentTitleOpts(title="Table-基本示例", subtitle='共有 '+str(data.shape[0]))
    )
    return tablel
