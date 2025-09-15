import pandas as pd
from sqlalchemy import create_engine
from pytdx.hq import TdxHq_API
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler
from  datetime import date

import sys
mon = date.today().strftime('%m')
year = date.today().strftime('%Y')
while mon in ('06','12'):
    sys.exit(0)

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
api = TdxHq_API()
api.connect('180.153.18.170', 7709)


match mon:
    case mon if mon <= '03':
        ls =['gpcw'+str(int(year)-1)+'1231.zip']
    case mon if '03'< mon <= '05':
        ls = ['gpcw'+str(int(year)-1)+'1231.zip', 'gpcw'+year+'0331.zip']
    case mon if '06'< mon <= '09':
        ls =['gpcw'+year+'0630.zip']
    case mon if '09'< mon < '12':
        ls =['gpcw'+year+'0930.zip']
    case mon if mon in ('06','12'):
        ls = []
datacrawler = HistoryFinancialCrawler()
pd.set_option('display.max_columns', None)

for i in ls:
    result = datacrawler.fetch_and_parse(reporthook=demo_reporthook, filename=i, path_to_download="/tmp/tmpfile.zip")
    dd = datacrawler.to_df(data=result)
    dd = dd[dd.columns[:582]]
    dd['report_date']= dd['report_date'].astype(object)
    upday = dd['report_date'].iloc[0]
    dd = dd.round(4)
    dd.to_sql(i[:12],eng,if_exists='replace')
    for j,l in enumerate(dd.index.values.tolist()):
        try:
            day = pd.read_sql(l, eng)['report_date'].tail(1).tolist()[0]
            if upday > day:
                pd.DataFrame(dd.iloc[j]).T.reset_index(drop=True).set_index('report_date').to_sql(l, eng, if_exists='append')
                
            else:
                print(l+'not Updated !')
                pass
        except:
            try:
                pd.DataFrame(dd.iloc[j]).T.reset_index(drop=True).set_index('report_date').to_sql(l, eng, if_exists='append')
                print(l+" =====  New Code add !!")
            except:
                pass

eng.dispose()
