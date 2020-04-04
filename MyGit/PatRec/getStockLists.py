import pandas as pd
import tushare as ts

df = ts.get_stock_basics()
df.to_csv('f:/WWWStocks/stockslist.csv', encoding='utf8')