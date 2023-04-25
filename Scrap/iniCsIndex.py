from sqlalchemy import create_engine
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

a = pd.read_excel('/home/ts/app/csIndex202205.xls').set_index('Index_code')
a.to_sql('csIndexs', eng, if_exists='replace')
print('CsIndex Upgrade !')