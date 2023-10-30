import pandas as pd
from sqlalchemy import create_engine
from pytdx.hq import TdxHq_API
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler


api = TdxHq_API()
api.connect('119.147.212.81', 7709)

StockId = '600001'
inf = api.to_df(api.get_company_info_category(1 , StockId))
i = 0
while i <=15 :
    try:
        data = api.to_df(api.get_company_info_content(1, StockId, inf.iloc[i][1], inf.iloc[i][2], inf.iloc[i][3]))
        file = 'g:\\tmp\\1\\'+ StockId + '_'+str(i) + '.txt'
        f = open(file=file, mode='w')
        f.write(data.value[0])
        f.close()
        i = i+1
    except:
        f.close()
        i = i + 1
        pass