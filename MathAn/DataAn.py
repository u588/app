import pandas as pd
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engFS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxFS')

StocksList = pd.read_sql('StocksList', eng).code
sl = pd.DataFrame(columns=['code'], dtype=object)
for i, j in enumerate(StocksList):
    try:
        df = pd.read_sql(j, engFS)
        dd = df['col1']-df['col1'].shift(1)
        if (dd.tail(2) > 0).all():
            sl.loc[i,'code'] = j
        else:
            print(j)
            pass
    except:
        pass

