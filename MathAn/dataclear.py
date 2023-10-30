import pandas as pd
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')

df = pd.read_sql('StocksDetail202310', eng)
df = pd.read_excel('g:/HugeGraphData/StocksManages.xlsx', dtype={'code':object})

df['cSH'] = df['cSH'].str.replace(',','、')
df['acSH'] = df['acSH'].str.replace(',','、')
df['ucSH'] = df['ucSH'].str.replace(',','、')

 
df.fillna('--', inplace=True)
n = len(df['code'])
i = 0

while i< n:
    try:
        df['cSH'][i] = df['cSH'][i].split('、')[0]+'、'+df['cSH'][i].split('、')[1]
        df['cSHr'][i] = df['cSHr'][i].split('、')[0]+'、'+df['cSHr'][i].split('、')[1]
        df['acSH'][i] = df['acSH'][i].split('、')[0]+'、'+df['acSH'][i].split('、')[1]
        df['acSHr'][i] = df['acSHr'][i].split('、')[0]+'、'+df['acSHr'][i].split('、')[1]
        df['ucSH'][i] = df['ucSH'][i].split('、')[0]+'、'+df['ucSH'][i].split('、')[1]
        df['ucSHr'][i] = df['ucSHr'][i].split('、')[0]+'、'+df['ucSHr'][i].split('、')[1]
        i = i + 1
    except:
        try:
            df['acSH'][i] = df['acSH'][i].split('、')[0]+'、'+df['acSH'][i].split('、')[1]
            df['acSHr'][i] = df['acSHr'][i].split('、')[0]+'、'+df['acSHr'][i].split('、')[1]
            df['ucSH'][i] = df['ucSH'][i].split('、')[0]+'、'+df['ucSH'][i].split('、')[1]
            df['ucSHr'][i] = df['ucSHr'][i].split('、')[0]+'、'+df['ucSHr'][i].split('、')[1]
            i = i+1
        except:
            try:
                df['ucSH'][i] = df['ucSH'][i].split('、')[0]+'、'+df['ucSH'][i].split('、')[1]
                df['ucSHr'][i] = df['ucSHr'][i].split('、')[0]+'、'+df['ucSHr'][i].split('、')[1]
                i = i +1      
            except:
                i = i +1 
                print(df['code'][i])
                pass



df['cSHl'] = df['cSH'].str.len()
df.set_index('code').to_excel('g:/hugegraphdata/StockDetail.xlsx')

while i < n :
    df['intro'][i]= df['intro'][i].split("；")[0]
    df['intro'][i]= df['intro'][i].split("。")[0]
    i = i+1
