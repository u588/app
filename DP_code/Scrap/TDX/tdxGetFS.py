import pandas as pd
from sqlalchemy import create_engine
from pytdx.hq import TdxHq_API
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler
from  datetime import date

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
api = TdxHq_API()
api.connect('119.147.212.81', 7709)

mon = date.today().strftime('%m')
year = date.today().strftime('%Y')
match mon:
    case mon if mon == '12':
        filename='gpcw'+year+'1231.zip'
    case mon if mon < '03':
        filename='gpcw'+year+'1231.zip'
    case mon if '03'<= mon < '06':
        filename='gpcw'+year+'0331.zip'
    case mon if '06'<= mon < '09':
        filename='gpcw'+year+'0630.zip'
    case mon if '09'<= mon < '12':
        filename='gpcw'+year+'0930.zip'

datacrawler = HistoryFinancialCrawler()
pd.set_option('display.max_columns', None)


result = datacrawler.fetch_and_parse(reporthook=demo_reporthook, filename=filename, path_to_download="/tmp/tmpfile.zip")
dd = datacrawler.to_df(data=result)
dd['report_date']= dd['report_date'].astype(object)
upday = dd['report_date'][0]
dd = dd.round(2)
for j,l in enumerate(dd.index.values.tolist()):
    try:
        day = pd.read_sql(l, eng)['report_date'].tail(1).tolist()[0]
        if upday > day:
            pd.DataFrame(dd.iloc[j]).T.reset_index(drop=True).set_index('report_date').to_sql(l, eng, if_exists='append')
            
        else:
            print(l+'not Updated !')
            pass
    except:
        print(l+" =====  Excepts !!")
        pass

eng.dispose()

