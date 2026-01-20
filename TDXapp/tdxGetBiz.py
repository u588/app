from mootdx.quotes import Quotes
import pandas as pd
import re
from sqlalchemy import create_engine, text
from datetime import datetime

new_BizP='BizP'+datetime.now().strftime('%Y%m')
new_mBiz='mBiz'+datetime.now().strftime('%Y%m')

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/StockBas')
engs = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxStocks')

# 原表改名为运行月份表
rawBizP = pd.read_sql('BizP',eng)
rawBizP.set_index('StockCode').to_sql(new_BizP, eng, if_exists='replace')

rawmBiz = pd.read_sql('mBiz',eng)
rawmBiz.set_index('日期').to_sql(new_mBiz, eng, if_exists='replace')

with eng.connect() as conn:
    conn.execute(text('DROP TABLE IF EXISTS "BizP" CASCADE;'))
    conn.execute(text('DROP TABLE IF EXISTS "mBiz" CASCADE;'))
    conn.commit()

def getBiz(StockCode, StockName):
    qf10='经营分析'
    client = Quotes.factory(market='std')
    txtRaw = client.F10(StockCode, qf10)

    txt = txtRaw.replace('│',' ')                
    txt = re.sub('([\u2500-\u25f7])','',txt)[116:]

    # StockName = re.findall(r'\b'+StockCode+'\s+([^\s]*)',txtRaw)[0]
    try:
        hc = re.findall(r'\d+.\d+|\d+%',re.findall(r'前5大客户[^\s]*',txt)[0])
        hp = re.findall(r'\d+\.\d+|\d+%',re.findall(r'前5大供应商[^\s]*',txt)[0])
        csdf = pd.DataFrame(hc+hp).T
        csdf.columns = ["营收额","营收占比",'采购额',"采购占比"]
        csdf['StockCode'] = StockCode
        csdf['StockName'] = StockName
        csdf[['StockCode','StockName',"营收额","营收占比",'采购额',"采购占比"]].set_index('StockCode').to_sql('BizP', eng, if_exists='append')

    except:
        pass

    fi = txt[txt.find('【2.主营构成分析】'):]
    ff = fi[:fi.find('【3.前5名客户营业收入表】')]
    datetimes=re.findall(r'截止日期:([^\s]*)', ff)
    dd = ff.replace('─','').splitlines(keepends=False)

    Data = pd.DataFrame(columns=())
    i = 0
    while i < len(dd):
        lis = re.split(r"\s+", dd[i])[-6:]
        if len(lis)!=6:
            i = i+1
            # pass
        else:
            df = pd.DataFrame(lis).T
            # df.columns=["股票名称", "一周涨跌幅%","一月涨跌幅%","三月涨跌幅%","半年涨跌幅%","一年涨跌幅%"]
            Data = pd.concat([Data, df],axis=0)
            i=i+1
    Data.reset_index(drop=True,inplace=True)
    Data = Data.replace('---',pd.NA)
    ddf  = Data
    # ddf  = Data.apply(pd.to_numeric, errors='ignore')

    ddfindex = ddf[ddf[0]=='项目名'].index
    raDF = pd.DataFrame(columns=['日期',"项目名","营业收入(元)","收入比例(%)","营业利润(元)","利润比例(%)","毛利率(%)"])

    for i in [0,1,2,3]:
        try:
            dfd = ddf.loc[(ddfindex[i]+1):(ddfindex[i+1]-1)].reset_index(drop=True)
            dfd.columns = ["项目名","营业收入(元)","收入比例(%)","营业利润(元)","利润比例(%)","毛利率(%)"]
            dfd['日期'] = datetimes[i]
            raDF = pd.concat([raDF,dfd], axis=0)
        except:
            continue

    raDF['StockCode'] = StockCode
    raDF['StockName'] = StockName
    raDF[['StockCode','StockName','日期',"项目名","营业收入(元)","收入比例(%)","营业利润(元)","利润比例(%)","毛利率(%)"]].set_index('日期').to_sql('mBiz', eng, if_exists='append')




StockList = pd.read_sql('StocksList', engs)[['code','name']]
n = 0
FailureList = []
while n < len(StockList):
    try:
        getBiz(StockList.iloc[n,0], StockList.iloc[n,1])
        print(StockList.iloc[n,0]+ 'OK !')
    except:
        print(StockList.iloc[n,0] + 'Failure ! ')
        FailureList.append(n)
        pass
    n = n + 1
StockList.iloc[FailureList].to_excel('/home/ts/app/TDXapp/Biz_FailureList.xlsx', index=False)
eng.dispose()
engs.dispose()
