import akshare as ak
from sqlalchemy import create_engine
import pandas as pd


engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')

df = pd.read_sql('akRawStockIC', engB)

tempdf = df[df['分类标准编码'].isin(['008001','008002','008003','008014'])].sort_values(by=['证券代码','分类标准编码'])
    
tempdf[['新证券简称','证券代码','分类标准', '变更日期','行业中类', '行业大类', '行业次类', '行业门类', '行业编码',
       '分类标准编码' ]].rename(columns={'新证券简称':'StockName','证券代码':'StockCode','分类标准':'ICS', '变更日期':'DP','行业中类':'IC4', '行业大类':'IC3', '行业次类':'IC2', '行业门类':'IC1', '行业编码':'ICode',
       '分类标准编码':'ICSCode' }).set_index('StockCode').to_sql('akStockIC', engB, if_exists='replace')

engB.dispose()
print('StockIC upgrade ! ')