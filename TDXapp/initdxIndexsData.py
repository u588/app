from sqlalchemy import create_engine
import pandas as pd
import tqdm

engI = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')

IndexLists = pd.read_sql('optIndexs', engI)[['IndexCode','IndexName']].values.tolist()
D = pd.DataFrame(columns=['IndexCode', 'IndexName','3D','5D','21D','55D','date']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})

for i in tqdm.tqdm(IndexLists):
    try:
        Data = pd.read_sql(i[0], engI)

        Data['3D'] = (Data['close'].pct_change(3)*100).round(2)
        Data['5D'] = (Data['close'].pct_change(5)*100).round(2)
        Data['21D'] = (Data['close'].pct_change(21)*100).round(2)
        Data['55D'] = (Data['close'].pct_change(55)*100).round(2)
        Data['date'] = Data['datetime'].str[:10]
        Data['IndexCode'] = i[0]
        Data['IndexName'] = i[1]
    except:
        pass
    df =  Data[['IndexCode', 'IndexName','3D','5D','21D','55D','date']].tail(55)
    D = pd.concat([D,df])
    
    
# D.sort_values(by=['date','IndexCode']).set_index('IndexCode').to_excel('/home/ts/app/TDXapp/tdxAppData/indexData.xlsx')
D.sort_values(by=['date','IndexCode']).set_index('IndexCode').to_sql('tdxIndexsData', engI, if_exists = 'replace')
engI.dispose()

