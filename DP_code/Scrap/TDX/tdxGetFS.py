import pandas as pd
from sqlalchemy import create_engine
from pytdx.hq import TdxHq_API
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
api = TdxHq_API()
api.connect('119.147.212.81', 7709)

# lsD = pd.read_excel('G:/Gitee/App/MathAn/tdxFSls.xlsx')
# ls = lsD['filename'].to_list()
ls = ['gpcw20230930.zip']

datacrawler = HistoryFinancialCrawler()
pd.set_option('display.max_columns', None)

for i in ls:
    result = datacrawler.fetch_and_parse(reporthook=demo_reporthook, filename=i, path_to_download="/tmp/tmpfile.zip")
    dd = datacrawler.to_df(data=result)
    dd['report_date']= dd['report_date'].astype(object)
    dd = dd.round(2)
    for j,l in enumerate(dd.index.values.tolist()):
        try:
            pd.DataFrame(dd.iloc[j]).T.reset_index(drop=True).set_index('report_date').to_sql(l, eng, if_exists='append')
            print(l+'Saved !')
        except:
            print(l+" =====  Not Saved !!")
            pass
eng.dispose()


