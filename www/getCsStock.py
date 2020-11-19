from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')
IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()


def getStock(Code):
    D = pd.read_sql('csIndexCons',eng)
    Data = D.loc[D['Index_name']== Code].reset_index(drop=True).to_json(orient='records')
    return Data
