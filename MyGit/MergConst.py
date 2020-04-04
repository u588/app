import pandas as pd

IndexLists = pd.read_csv('f:/tdxindexlistall.csv', dtype={'index_code':object})
StockLists = pd.read_csv('f:/stocklist.csv', dtype={'code':object})

IndexConst = pd.read_csv('f:/indexconst.csv', dtype={'index_code':object,'code':object})

indexs = IndexLists.index_code.tolist()

for i, index in enumerate(indexs):
    print('Index', i, '/', len(indexs))
    try:
        IndexConst.loc[IndexConst['index_code']==index, 'index_name']= IndexLists.index_name[i]
        print(index)
        print(IndexLists.index_name[i],'merged !')

               
    except:
        pass


stocks = StockLists.code.tolist()
for i, stock in enumerate(stocks):
    print('Stock', i, '/', len(stocks))
    try:
        IndexConst.loc[IndexConst['code']==stock, 'name']= StockLists.name[i]
        print(stock)
        print(StockLists.name[i],'merged !')
    except:
        pass
IndexConst.set_index('index_code', inplace=True)
IndexConst.to_csv('f:/1.csv', encoding='utf8')
