import pandas as pd

Indexs = pd.read_excel('G:/Gitee/App/tdxAppData/tdxIndexsCode.xlsx', dtype={'IndexCode':object})
Stocks = pd.read_excel('G:/Gitee/App/tdxAppData/tdxSocksCode.xlsx', dtype={'StockCode':object})

Cons = pd.read_excel('G:/Gitee/App/tdxAppData/tdxGuiIndexCons622.xlsx', dtype={'IndexCode':object, 'StockCode':object})


n = 0
while n < Cons.shape[0]:
    try:
        Cons.loc[[n],['IndexName']] = Indexs.IndexName[Indexs.IndexCode==Cons.loc[n][0]].tolist()[0]
        Cons.loc[[n],['StockName']] = Stocks.StockName[Stocks.StockCode==Cons.loc[n][1]].tolist()[0]
        print(str(n)+ ' ok !')
        n = n + 1
    except:
        n = n + 1
    
Cons.dropna().set_index('IndexCode').to_excel('G:/Gitee/App/tdxAppData/tdxGuiIndexConsMerg622.xlsx')















IndexNames = Indexs.IndexName.tolist()

for i, index in enumerate(IndexNames):
    print('Index', i, '/', len(IndexNames))
    try:
        Cons.loc[Cons['IndexName']==index, 'IndexCode']= Indexs.IndexCode[i]
        print(index)
        print(Indexs.IndexCode[i],'merged !')        
    except:
        pass


Cons = pd.read_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/tdxIndexCons.xlsx', dtype={'code':object})
Indexs = pd.read_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/tdxChenger.xlsx')

IndexNames = Indexs.bname.tolist()

for i, index in enumerate(IndexNames):
    print('Index', i, '/', len(IndexNames))
    try:
        Cons.loc[Cons['IndexName']==index, 'IndexName']= Indexs.aname[i]
        print(index)
        print(Indexs.Index_code[i],'merged !')        
    except:
        pass



s = pd.read_excel('f:/tdxrawdata/ok/stockscode.xlsx',dtype={'StockCode':'object'})
c = pd.read_excel('f:/tdxrawdata/ok/tdxindexcons.xlsx',dtype={'StockCode':'object','StockName':'object'})

n = s.shape[0]
while i < n :
    try:
        c.loc[c.StockCode == s.loc[i][1] , 'StockName'] = s.loc[i][4]
        i = i+1
    except:
        i = i+1
        pass
    print(i)

