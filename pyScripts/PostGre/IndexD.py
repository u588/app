from sqlalchemy import create_engine
import tushare as ts
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/csIndex')


def GetIndex(cIndex):
    ciIndex = ts.get_h_data(code=cIndex, index=True)
    if cIndex.empty:
        pass
   
    else: 
        ciIndex = ciIndex.set_index('date')
        if pd.io.sql.has_table(cIndex, eng):
            history = pd.read_sql(cIndex, eng)
            stamp = history.tail(1)['date'].tolist()[0]
            ciIndex = ciIndex[(ciIndex['date']>stamp)]
        ciIndex.set_index(['date'], inplace=True)
        pd.io.sql.to_sql(ciIndex, cIndex, eng, if_exists='append')
 #       print ('intraday for ['+cIndex+'] got.')


IndexCodes = pd.read_sql('IndexList', eng)
IndexCodes = IndexCodes[1:].code.tolist()

for i, IndexCode in enumerate(IndexCodes):
    try:
        print ('Index', i, '/', len(IndexCodes))
        GetIndex(IndexCode)
#        print ('CsIndex for ['+IndexCode+'] got.')

    except:
        pass

#    if i>2:
#        break


