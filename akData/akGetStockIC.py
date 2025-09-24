import akshare as ak
from sqlalchemy import create_engine
import pandas as pd
from tqdm import tqdm

engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')

StockLists=pd.read_sql('akStocksList', engS)['StockCode'].to_list()
# StockLists = pd.read_excel('G:/Gitee/App/TDXapp/tdxAppData/akStocksList.xlsx', dtype={'StockCode':object})['StockCode'].to_list()

df = pd.DataFrame(columns=['新证券简称', '行业中类', '行业大类', '行业次类', '行业门类', '机构名称', '行业编码', '分类标准','分类标准编码', '证券代码', '变更日期'], dtype=object)
for i in tqdm(StockLists[:2500]):
    tempdf = ak.stock_industry_change_cninfo(symbol=i, start_date="11000101", end_date="22000101")
    tempdf = tempdf[tempdf['分类标准编码'].isin(['008001','008002','008003','008014'])].sort_values(by='分类标准编码')
    df = pd.concat([df,tempdf])
    # print(i+ ' concat !')
    
ddf = df[['新证券简称','证券代码','分类标准', '变更日期','行业中类', '行业大类', '行业次类', '行业门类', '行业编码',
    '分类标准编码' ]].rename(columns={'新证券简称':'StockName','证券代码':'StockCode','分类标准':'ICS', '变更日期':'DP','行业中类':'IC4', '行业大类':'IC3', '行业次类':'IC2', '行业门类':'IC1', '行业编码':'ICode',
    '分类标准编码':'ICSCode' })

# ddf.drop_duplicates(subset=(['StockCode','ICS']),keep='last').set_index('StockCode').to_excel('G:/Gitee/App/akData/akStockIC.xlsx')
ddf.drop_duplicates(subset=(['StockCode','ICS']),keep='last').set_index('StockCode').to_sql('akStockIC1', engB, if_exists='replace')

engB.dispose()
engS.dispose()
print('StockIC upgrade ! ')