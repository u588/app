import pandas as pd
from sklearn import preprocessing
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')
from d3blocks import D3Blocks




def d3(CodeId):
   df = pd.read_sql(CodeId, eng).reset_index(drop=True).reset_index()
   StocksList = pd.read_sql('StocksDetail20236', engB)
   St = StocksList.loc[StocksList['code']==CodeId]
   # Load d3blocks
   # from d3blocks import D3Blocks
   #
   # Initialize
   d3 = D3Blocks()
   #
   # Load example data
   # df = d3.import_example('cancer')
   #
   # Set size and tooltip

   # size = df['survival_months'].fillna(1).values / 20
   size =  ((preprocessing.minmax_scale(df.vol))*38).round(2)
   # tooltip = df['labx'].values + ' <br /> Survival: ' + df['survival_months'].astype(str).str[0:4].values
   tooltip = 'Date: '+df['datetime'].str[:10]+' <br /> Close: '+df['close'].astype(str).values + ' <br /> vol: ' + df['vol'].astype(str).values
   #
   # Scatter plot
   d3.scatter(df['index'].values,
                  df['close'].values,
                  size=size,
                  color=df['close'].astype(str).values,
                  stroke='#000000',
                  opacity=0.4,
                  tooltip=tooltip,
               #    scale='true',
                  title=St.name.to_list()[0]+' : '+St.code.to_list()[0],
                  figsize=[1800,700],
                  filepath='/home/static/d3plt.html',
                  cmap='tab20c')
   
