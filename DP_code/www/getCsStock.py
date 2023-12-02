from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')
engT = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')
IndexLists = pd.read_sql('tdxIndexs', eng).IndexCode.to_list()
eng.dispose()

def getStock(Code,ID):
    D = pd.read_sql('IndexCons',eng)
    eng.dispose()
    d = pd.DataFrame(columns=['code','PCB']).astype(dtype={'PCB':float})
    n = int(ID.strip('D'))
    Data = D.loc[D['IndexName']== Code].reset_index(drop=True)
    StockLists = Data['StockCode'].to_list()
    for Stock in StockLists:
        try:
            DD = pd.read_sql(Stock, engT)
            dd =  pd.DataFrame(columns=['code','PCB']).astype(dtype={'PCB':float})


            dd['code'] = [Stock] 
            dd['PCB'] = [(DD.close.pct_change(1)*100).tail(n).sum().round(2)]
            dd.reset_index(drop=True, inplace =True)

            # d = d.append(dd[['code','PCB']])
            d = pd.concat([d, dd[['code','PCB']]])
        except:
            pass

    d.sort_values(by='PCB', ascending=0, inplace=True)
    data = d.to_json(orient='records')
    engT.dispose()
    return data
