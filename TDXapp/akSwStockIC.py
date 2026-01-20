import akshare as ak
from sqlalchemy import create_engine
import pandas as pd

engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')

Stocks = pd.read_sql('StocksList', engS)
# 获取申万行业分类
swRAW = ak.stock_industry_category_cninfo(symbol="申银万国行业分类标准")[['类目编码', '类目名称', '终止日期',  '父类编码', '分级']]
# 获取申万行业分类历史数据
swStockICRAW = ak.stock_industry_clf_hist_sw().sort_values(by=['symbol','start_date'], ascending=[True,False]).drop_duplicates(subset=['symbol'], keep='first')

code_to_info = swRAW.set_index('类目编码')[['类目名称', '父类编码']].to_dict('index')

# 2. 定义函数：输入不带 'S' 的三级编码，返回 (IC1, IC2, IC3)
def get_ic_levels(third_code_raw):
    third_code = 'S' + str(third_code_raw).strip()  # 确保转为字符串并加 'S'
    
    # 第三级
    if third_code not in code_to_info:
        return pd.NA, pd.NA, pd.NA
    ic3_name = code_to_info[third_code]['类目名称']
    second_code = code_to_info[third_code]['父类编码']
    
    # 第二级
    if second_code not in code_to_info:
        return pd.NA, pd.NA, ic3_name
    ic2_name = code_to_info[second_code]['类目名称']
    first_code = code_to_info[second_code]['父类编码']
    
    # 第一级
    if first_code not in code_to_info:
        return pd.NA, ic2_name, ic3_name
    ic1_name = code_to_info[first_code]['类目名称']
    
    return ic1_name, ic2_name, ic3_name

ic_tuples = swStockICRAW['industry_code'].apply(get_ic_levels)
swStockICRAW[['IC1', 'IC2', 'IC3']] = pd.DataFrame(ic_tuples.tolist(), index=swStockICRAW.index)

df = Stocks[['code', 'name', 'area','market','list_date', 'act_name', 'act_ent_type']].merge(swStockICRAW[['symbol', 'IC1','IC2', 'IC3']], left_on='code', right_on='symbol', how='left').drop(columns=['symbol']).rename(columns={'code':'StockCode', 'name':'StockName','list_date':'ListDate', 'area':'Area', 'market':'Market', 'act_name':'ActName', 'act_ent_type':'ActEntType '})

df.to_sql('swStockIC', engB, if_exists='replace', index=False)
print("申万行业分类数据已成功写入 StockBas 数据库的 swStockIC 表中。")