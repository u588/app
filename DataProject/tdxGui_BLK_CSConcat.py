import pandas as pd


BLKCons = pd.read_excel('G:/Gitee/App/tdxAppData/1tdxIndexsConsBLK.xlsx', dtype={'IndexCode':object, 'StockCode':object})
CsCons = pd.read_excel('G:/Gitee/App/tdxAppData/1csIndexCons.xlsx', dtype={'IndexCode':object, 'StockCode':object})
GUICons = pd.read_excel('G:/Gitee/App/tdxAppData/1tdxGuiIndexCons.xlsx', dtype={'IndexCode':object, 'StockCode':object})

df = pd.DataFrame
df = pd.concat([CsCons, BLKCons])
df = pd.concat([df,GUICons])

df.drop_duplicates().set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/FinaltdxIndexCons622.xlsx')