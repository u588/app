import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/FindStocks')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

FindStocks = pd.read_sql('FindStocks', eng)
gpFS = FindStocks.groupby('datetime')
gpList = list(gpFS.groups)

D = pd.DataFrame(columns=['StockCode', 'StockName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})
for dt in gpList:
    df = gpFS.get_group(dt).reset_index(drop=True)
    for sc in list(df.code):
        sr = pd.read_sql(sc, engs)
        ss = sr.loc[sr['datetime'] >= (dt + ' 15:00')]
        d  = pd.DataFrame(columns=['StockCode', 'StockName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})
        d['3D'] = [(ss.close.pct_change(1)*100).tail(3).sum().round(2)]
        d['5D'] = [(ss.close.pct_change(1)*100).tail(5).sum().round(2)]
        d['21D'] = [(ss.close.pct_change(1)*100).tail(21).sum().round(2)]
        d['55D'] = [(ss.close.pct_change(1)*100).tail(55).sum().round(2)] 
        d['StockCode'] = sc
        d['StockName'] = df.loc[df['code'] == sc].name.tolist()[0]
        D = pd.concat([D,d])


def get(code):
    dt = gpList[code]
    df = gpFS.get_group(dt).reset_index(drop=True)
    print(dt)
    D = pd.DataFrame(columns=['StockCode', 'StockName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})
    for sc in list(df.code):
        sr = pd.read_sql(sc, engs)
        ss = sr.loc[sr['datetime'] >= (dt + ' 15:00')]
        d  = pd.DataFrame(columns=['StockCode', 'StockName','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})
        d['3D'] = [(ss.close.pct_change(1)*100).head(3).sum().round(2)]
        d['5D'] = [(ss.close.pct_change(1)*100).head(5).sum().round(2)]
        d['21D'] = [(ss.close.pct_change(1)*100).head(21).sum().round(2)]
        d['55D'] = [(ss.close.pct_change(1)*100).head(55).sum().round(2)] 
        d['StockCode'] = sc
        d['StockName'] = df.loc[df['code'] == sc].name.tolist()[0]
        D = pd.concat([D,d])
        D.reset_index(drop=True, inplace=True)
    return D
        
    
D.describe()