import pandas as pd
from sqlalchemy import create_engine

# eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/Funds')
# engs = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')
eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

StockLists = pd.read_sql('csIndexs', eng).Index_code.tolist()

for i, CodeID in enumerate(StockLists):
    print('Index', i, '/', len(StockLists))
    # if StockCode >= '603885':
    try:
        df = pd.read_sql(CodeID, eng)
        df.drop_duplicates(subset='date', keep='first', inplace=True)

        df.set_index('date', inplace=True)
        df.to_sql(CodeID, eng, if_exists='replace')
        print(CodeID,'saved to sql !')
    except:
        pass

