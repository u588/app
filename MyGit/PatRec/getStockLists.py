import pandas as pd
import tushare as ts

df = ts.get_stock_basics()
df.to_csv('/home/ts/app/www/html/stockslist.csv', encoding='utf8')