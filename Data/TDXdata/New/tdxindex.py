import pandas as pd
a = pd.read_excel("/home/ts/app/Data/TDXdata/New/tdxIndexsCon.xlsx", dtype={'IndexCode':object, 'StockCode':object})
b = a.groupby('IndexCode').count()
aa = a.drop_duplicates(subset='IndexCode')
aa.set_index('IndexCode', inplace=True)
aa.loc[:, 'Num'] = b.IndexName