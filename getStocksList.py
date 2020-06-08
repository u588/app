import tushare as  ts
import pandas as pd

data = ts.get_stock_basics().round(2)

if len(data)>3800:
    data.to_csv('/home/ts/app/data/StocksList.csv')
else:
    pass