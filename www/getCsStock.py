from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')
engT = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxStocks')
IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()


def getStock(Code,ID):
    D = pd.read_sql('csIndexCons',eng)
    d = pd.DataFrame(columns=['code','PCB']).astype(dtype={'PCB':float})
    n = int(ID[0])
    Data = D.loc[D['Index_name']== Code].reset_index(drop=True)
    StockLists = Data['code'].to_list()
    for Stock in StockLists:
        try:
                
            DD = pd.read_sql(Stock, engT).tail(n)
            DD['PCB'] = ((DD.close-DD.open)/DD.open*100).round(2)
            dd = DD.head(1)[['open','close']]
            dd['code'] = Stock
            dd['PCB'] = DD['PCB'].sum().round(2)
            dd.reset_index(drop=True, inplace =True)

            # d = d.append(dd[['code','PCB']])
            d = pd.concat([d, dd[['code','PCB']]])
        except:
            pass

    d.sort_values(by='PCB', ascending=0, inplace=True)
    data = d.to_json(orient='records')
    return data
