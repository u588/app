import tushare as  ts
import pandas as pd

data = ts.get_stock_basics().round(2)

data.to_csv('/home/ts/app/data/StocksList.csv')