import tushare as ts
import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

token = 'eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7'
pro = ts.pro_api(token=token)

data = pd.read_sql('csIndexs', eng)
IndexLists = (data.Index_code +'.'+ data.Market).to_list()


