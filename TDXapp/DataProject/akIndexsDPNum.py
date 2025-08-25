import akshare as ak
from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')

indexDP = ak.index_stock_info().rename(columns={'index_code':'IndexCode', 'display_name':'IndexName','publish_date':'DP'})
indexDP.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/indexDP.xlsx')

indexNum = ak.index_all_cni()[['指数代码','指数简称','样本数']].rename(columns={'指数代码':'IndexCode','指数简称':'IndexName','样本数':'Num'})
indexNum.set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/indexNum.xlsx')
print('ok !')