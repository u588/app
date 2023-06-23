from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')

Data = pd.read_sql('
                   
                   ', eng)
IndexLists = Data.loc[~(Data.IndexSTL=='市场总览')]
n = IndexLists.shape[0]
i = 0
D = pd.DataFrame(columns=['IndexCode', 'IndexName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})

while i < n :
    try:
        Data = pd.read_sql(IndexLists.loc[i][0], eng)
        d  = pd.DataFrame(columns=['IndexCode', 'IndexName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})
        d['IndexCode'] = [IndexLists.loc[i][0]]
        d['IndexName'] = [IndexLists.loc[i][1]]

        d['3D'] = [(Data.close.pct_change(1)*100).tail(3).sum().round(2)]
        d['5D'] = [(Data.close.pct_change(1)*100).tail(5).sum().round(2)]
        d['21D'] = [(Data.close.pct_change(1)*100).tail(21).sum().round(2)]
        d['55D'] = [(Data.close.pct_change(1)*100).tail(55).sum().round(2)]       

        D = pd.concat([D,d])
        print(IndexLists.loc[i][0] + ' Concated !')
        i = i + 1

    except:
        i = i + 1
        pass

D.set_index('IndexCode').to_sql('tdxIndexsData', eng, if_exists = 'replace')


