from sqlalchemy import create_engine
import pandas as pd
import streamlit as st

eng = create_engine('postgresql+psycopg://sa:11111111@10.145.254.56:5432/tdxIndex')
engT = create_engine('postgresql+psycopg://sa:11111111@10.145.254.56:5432/tdxStocks')
IndexLists = pd.read_sql('optIndexs', eng).IndexCode.to_list()

@st.cache_data
def getStock(Code):
    D = pd.read_sql('IndexCons',eng)
    df = pd.DataFrame(columns=['StockCode', 'StockName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float}) 
    Data = D.loc[D['IndexCode']== Code].reset_index(drop=True)
    StockLists = Data[['StockCode','StockName']].values.tolist()
    for Stock in StockLists:
        try:
            DD = pd.read_sql(Stock[0], engT)
            dd = pd.DataFrame(columns=['StockCode', 'StockName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})
            dd['3D'] = [(DD.close.pct_change(1)*100).tail(3).sum().round(2)]
            dd['5D'] = [(DD.close.pct_change(1)*100).tail(5).sum().round(2)]
            dd['21D'] = [(DD.close.pct_change(1)*100).tail(21).sum().round(2)]
            dd['55D'] = [(DD.close.pct_change(1)*100).tail(55).sum().round(2)]
            dd['StockCode'] = Stock[0] 
            dd['StockName'] = Stock[1]
            dd.reset_index(drop=True, inplace =True)
            # d = d.append(dd[['code','PCB']])
            df = pd.concat([df, dd])
        except:
            pass
    df.sort_values(by='3D', ascending=0, inplace=True)
    df.reset_index(drop=True,inplace=True)
    # data = d.to_json(orient='records')
    return df
