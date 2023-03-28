from sqlalchemy import create_engine
import tushare as ts
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MarkCap')

try:
    tsTop = ts.inst_detail().sort_values('date')
    upDay = tsTop.tail(1)['date'].to_list()[0]
    hiDay = pd.read_sql('tsInstList', eng).tail(1)['date'].to_list()[0]
    tsTop[tsTop['date']>hiDay].drop_duplicates(subset='code').set_index('date').to_sql('tsInstList',eng, if_exists='append')
except:
    pass

print ('每日机构成交明细 ok')
