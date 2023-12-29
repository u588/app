import pandas as pd
from sqlalchemy import create_engine
import numpy as np

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engAn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/DataAn')

gm = pd.read_sql('gm', engAn)
engAn.dispose()

gr = gm.groupby('lev4_code')
grList = gr.size().index.to_list()

gr.get_group(grList[0])

