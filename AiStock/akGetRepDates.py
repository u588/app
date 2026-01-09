import akshare as ak
from sqlalchemy import create_engine
import pandas as pd
from tqdm import tqdm

engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
# engS = create_engine('postgresql+psycopg://sa:11111111@111.61.77.88:65123/qfqStock')
# engI = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')
# engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')
engF = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxFS')


StockList = pd.read_sql('StocksList', engS)


cl = ['年报', '半年报', '一季报', '三季报']
# df = pd.DataFrame()
for code in tqdm(StockList['code'].tolist()):
    dff = pd.DataFrame()
    for category in cl:
        try:
            dftmp = ak.stock_zh_a_disclosure_report_cninfo(symbol=code, market="沪深京", category=category, start_date="19990101", end_date="20301231")[['代码', '简称', '公告时间']]
            dff = pd.concat([dff, dftmp])
        except:
            continue
    if dff.empty:
        continue
    else:
        dff['公告时间'] = dff['公告时间'].astype(str).str[:10]
        dff.drop_duplicates(subset=['公告时间']).sort_values(by='公告时间',ascending=True).to_sql('fsDP', engF, if_exists='append', index=False)
# df.set_index('代码').to_excel('./AllStockReportDates.xlsx')

