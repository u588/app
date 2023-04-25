from sqlalchemy import create_engine
import tushare as ts
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MarkCap')

try:
    tsTop = ts.top_list().drop_duplicates(subset='code')
    upDay = tsTop.tail(1)['date'].to_list()[0]
    hiDay = pd.read_sql('tsTopList', eng).tail(1)['date'].to_list()[0]
    if upDay > hiDay:
        tsTop.set_index(['date'], inplace=True)
        tsTop.to_sql('tsTopList', eng, if_exists='append')
    else:
        pass
except:
    pass

print ('每日龙虎榜 ok')
