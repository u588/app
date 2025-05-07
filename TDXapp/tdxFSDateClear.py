import pandas as pd
from sqlalchemy import create_engine
from pytdx.hq import TdxHq_API
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler

# import adbc_driver_postgresql.dbapi as pg_dbapi

# uri = "postgresql://sa:11111111@10.3.18.56:5432/tdxFS"
# conn = pg_dbapi.connect(uri)

conn = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
api = TdxHq_API()
api.connect('119.147.212.81', 7709)

ls = ['gpcw20241231.zip']
datacrawler = HistoryFinancialCrawler()
pd.set_option('display.max_columns', None)


result = datacrawler.fetch_and_parse(reporthook=demo_reporthook, filename=ls[0], path_to_download="/tmp/tmpfile.zip")
dd = datacrawler.to_df(data=result)

for j,l in enumerate(dd.index.values.tolist()):
    try:
        raw = pd.read_sql(l, conn)
        day = raw['report_date'].tail(1).tolist()[0]
        if day == 20250331 :
            pp = raw.drop(raw.tail(1).index)
            pp.set_index('report_date').to_sql(l, conn, if_exists='replace')
            print('droped !')
            
        else:
            print(l+'not Updated !')
            pass
    except:
        print(l+" =====  Excepts !!")
        pass

conn.dispose()
