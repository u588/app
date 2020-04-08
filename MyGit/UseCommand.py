from sqlalchemy import create_engine
import pandas as pd
import tushare as ts


ts.set_token('eee11f7ac92d7b2eed02dadb10d1ddfed44cee3b458dffb6f3fe7ba7')
pro = ts.pro_api()

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/csIndex')
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')


from pytdx.hq import TdxHq_API


api = TdxHq_API()
api = TdxHq_API(heartbeat=True)
api.connect('119.147.212.81', 7709)

"""
category(K线种类): 5分钟K线(0), 1分钟K线(8), 日K线(9)

"""

api.to_df(api.get_security_bars(Cate, 1, StockCode, start, 500))

api.to_df(api.get_security_list(1, 0))

api.to_df(api.get_xdxr_info(1,'600300'))

# 改变类型 解决以000开头的编码不显示问题
pd.read_excel('f:/IndexList.xls', dtype={'index_code':object})

xdxr_data.index = pd.DatetimeIndex(xdxr_data.index)


df = pd.DataFrame({'datetime':'', 'var':[]})