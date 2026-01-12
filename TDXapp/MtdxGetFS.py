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
年报（1231） 1.1--4.30  一季报（0331）4.1--4.30 中报（0630）7.1--8.30 三季报（0930）10.1--10.31

/home/ts/app/JupLab/getFSlist.ipynb
数据更新==>年报、一季报（5.15）中报（9.15）三季报（11.15） 

gpcw2024.zip 1231 0930 0630 0331

2024.2.21 5218
2024.3.25 346077
2024.5.12  --> gpcw20240331.zip 4786722
2024.6.21  --> gpcw20240331.zip 4788337
2024.9.16  --> gpcw20240331.zip 4806195
2024.9.16  --> gpcw20240630.zip 5389032

2025.5.7

gpcw20241231.zip --> 5539530
gpcw20250331.zip --> 4856246

2025.8.30
gpcw20241231.zip --> 5592670
gpcw20250331.zip --> 4954542
gpcw20250630.zip --> 5525448
gpcw20250930.zip -->

'''



ls = ['gpcw20250331.zip']
datacrawler = HistoryFinancialCrawler()
pd.set_option('display.max_columns', None)

for i in ls:
    result = datacrawler.fetch_and_parse(reporthook=demo_reporthook, filename=i, path_to_download="/tmp/tmpfile.zip")
    dd = datacrawler.to_df(data=result)
    dd = dd[dd.columns[:582]]
    dd['report_date']= dd['report_date'].astype(object)
    upday = dd['report_date'].iloc[0]
    dd = dd.round(2)
    dd.to_sql(i[:12],conn,if_exists='replace')
    for j,l in enumerate(dd.index.values.tolist()):
        try:
            day = pd.read_sql(l, conn)['report_date'].tail(1).tolist()[0]
            if upday > day:
                print(l + 'Updated !')
                pd.DataFrame(dd.iloc[j]).T.reset_index(drop=True).set_index('report_date').to_sql(l, conn, if_exists='append')
                
            else:
                print(l+'not Updated !')
                pass
        except:
            try:
                pd.DataFrame(dd.iloc[j]).T.reset_index(drop=True).set_index('report_date').to_sql(l, conn, if_exists='append')
                print(l+" =====  New Code add !!")
            except:
                pass

conn.dispose()

