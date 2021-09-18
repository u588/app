import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')
# date = 3D 5D 21D
def csIndexData(date):
    d = pd.read_sql('csIndexsData', eng)
    data = d.sort_values(by=date).head(10).append(d.sort_values(by=date).tail(10))[['Index_code','Index_name', date]].reset_index(drop=True)

    dd = data[['Index_name','Index_code', date]].sort_values(date, ascending=0).to_json(orient='records')
    return dd