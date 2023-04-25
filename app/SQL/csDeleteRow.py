import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

codeId = '931556'

sql = 'DELETE FROM "csIndexs" WHERE "Index_code" =\''+codeId+'\';'

#        sql ='DELETE FROM "'+codeId+'" WHERE datetime= \'2021-07-16 15:00\' ;'


result = eng.execute(sql)