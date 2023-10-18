import pandas as pd

df = pd.read_excel('g:/HugeGraphData/StocksManages.xlsx', dtype={'code':object})
n = len(df['code'])
i = 0
while i < n :
    df['intro'][i]= df['intro'][i].split("；")[0]
    df['intro'][i]= df['intro'][i].split("。")[0]
    i = i+1
