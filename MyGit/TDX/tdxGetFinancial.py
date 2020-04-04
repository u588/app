from pytdx.crawler.history_financial_crawler import HistoryFinancialListCrawler
import pandas as pd
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler
from pytdx.reader import HistoryFinancialReader
from pytdx.reader import BlockReader
from sqlalchemy import create_engine


home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxFinan')

crawler = HistoryFinancialListCrawler()
FinancialLists = pd.DataFrame(crawler.fetch_and_parse())['filename'].tolist()

datacrawler = HistoryFinancialCrawler()
#pd.set_option('display.max_columns', 10)
for i, files in enumerate(FinancialLists):
    try:
        print('Financial', i, '/', len(FinancialLists))
        result = datacrawler.fetch_and_parse(reporthook=demo_reporthook, filename=files, path_to_download='f:/'+files)
        df = datacrawler.to_df(data=result)
        df.to_sql(files[4:12], eng)
        print(files[4:12],'Financial Files got !')
    except:
        pass



# HistoryFinancialReader().get_df('f:/tmpfile.zip')





