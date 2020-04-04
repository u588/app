import pandas as pd

IndexLists = pd.read_csv('f:/constindex.csv', dtype={'index_code':object})
IndexListAll = pd.read_csv('f:/tdxindexlistall.csv', dtype={'index_code':object})

merg = pd.concat([IndexLists,IndexListAll], sort=False)
m = merg.drop_duplicates(subset='index_code', keep=False)
m.set_index('index_code', inplace=True)
m.to_csv('f:/IndexRemoveList2.csv', encoding='utf8')
