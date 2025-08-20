from sqlalchemy import create_engine
import akshare as ak
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56/tdxStocks')

StockListSH = ak.stock_info_sh_name_code()[['证券代码','证券简称','上市日期']].rename(columns={'证券代码':'StockCode','证券简称':'StockName','上市日期':'LPD'})
StockListSH['Market'] = '主板'

StockListKC = ak.stock_info_sh_name_code('科创板')[['证券代码','证券简称','上市日期']].rename(columns={'证券代码':'StockCode','证券简称':'StockName','上市日期':'LPD'})
StockListKC['Market'] = '科创板'

StockListSZ = ak.stock_info_sz_name_code()[['A股代码','A股简称','A股上市日期','板块']].rename(columns={'A股代码':'StockCode','A股简称':'StockName','A股上市日期':'LPD','板块':'Market'})

akStockLists = pd.concat([StockListSH,StockListKC,StockListSZ])

akStockLists.to_sql('akStocksList', eng, if_exists='replace')