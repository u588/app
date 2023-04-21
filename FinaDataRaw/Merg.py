import pandas as pd

Indexs = pd.read_excel('F:/FinaDataRaw/TDXdata/tdxIndexs.xlsx', dtype={'Index_code':object})
Cons = pd.read_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/tdxIndexCons1.xlsx', dtype={'code':object})



IndexNames = Indexs.Index_name.tolist()

for i, index in enumerate(IndexNames):
    print('Index', i, '/', len(IndexNames))
    try:
        Cons.loc[Cons['Index_name']==index, 'Index_Code']= Indexs.Index_code[i]
        print(index)
        print(Indexs.Index_code[i],'merged !')        
    except:
        pass


Cons = pd.read_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/tdxIndexCons.xlsx', dtype={'code':object})
Indexs = pd.read_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/tdxChenger.xlsx')

IndexNames = Indexs.bname.tolist()

for i, index in enumerate(IndexNames):
    print('Index', i, '/', len(IndexNames))
    try:
        Cons.loc[Cons['Index_name']==index, 'Index_name']= Indexs.aname[i]
        print(index)
        print(Indexs.Index_code[i],'merged !')        
    except:
        pass




