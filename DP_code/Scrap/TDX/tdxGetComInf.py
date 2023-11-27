import pandas as pd
from sqlalchemy import create_engine
from pytdx.hq import TdxHq_API
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler

engs = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxStocks')
StockLists =  pd.read_sql('StocksList', engs).code.tolist()

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
api = TdxHq_API()
api.connect('119.147.212.81', 7709)


api.to_df(api.get_company_info_category(0 , '000001'))
api.to_df(api.get_company_info_content(0, '000001', '000001.txt', 877195, 49773))
api.to_df(api.get_company_info_content(0, sl[0], inf.iloc[0][1], inf.iloc[0][2], inf.iloc[0][3]))

engs.dispose()
eng.dispose()