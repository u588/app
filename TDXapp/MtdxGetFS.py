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


'''
检查系统更新
import pandas as pd 
from pytdx.crawler.history_financial_crawler import HistoryFinancialListCrawler
crawler = HistoryFinancialListCrawler()
list_data = crawler.fetch_and_parse()
print(pd.DataFrame(data=list_data))


2024.2.21 5218
2024.3.25 346077
2024.5.12  --> gpcw20240331.zip 4786722

gpcw2024.zip 1231 0930 0630 0331

'''

ls = ['gpcw20240330.zip']
datacrawler = HistoryFinancialCrawler()
pd.set_option('display.max_columns', None)

for i in ls:
    result = datacrawler.fetch_and_parse(reporthook=demo_reporthook, filename=i, path_to_download="/tmp/tmpfile.zip")
    dd = datacrawler.to_df(data=result)
    dd['report_date']= dd['report_date'].astype(object)
    upday = dd['report_date'][0]
    dd = dd.round(2)
    for j,l in enumerate(dd.index.values.tolist()):
        try:
            day = pd.read_sql(l, conn)['report_date'].tail(1).tolist()[0]
            if upday > day:
                pd.DataFrame(dd.iloc[j]).T.reset_index(drop=True).set_index('report_date').to_sql(l, conn, if_exists='append')
                
            else:
                print(l+'not Updated !')
                pass
        except:
            print(l+" =====  Excepts !!")
            pass

conn.dispose()

