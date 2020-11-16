import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')
IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()

for i, CodeID in enumerate(IndexLists):
    print('Index', i, '/', len(IndexLists))
    # if StockCode >= '603885':
    try:
        df = pd.read_sql(CodeID, eng)
        df.drop_duplicates(subset='Date', keep='first', inplace=True)

        df.set_index('Date', inplace=True)
        df.to_sql(CodeID, eng, if_exists='replace')
        print(CodeID,'saved to sql !')
    except:
        pass

