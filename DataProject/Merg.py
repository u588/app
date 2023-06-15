import pandas as pd

Indexs = pd.read_excel('F:/FinaDataRaw/TDXdata/tdxIndexs.xlsx', dtype={'Index_code':object})
Cons = pd.read_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/tdxIndexCons1.xlsx', dtype={'code':object})



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

