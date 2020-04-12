from sqlalchemy import create_engine
import pandas as pd


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/csIndex')

IndexCodes = pd.read_sql('IndexList', eng)[1:].code.tolist()
Constituents = pd.DataFrame
for i, IndexCode in enumerate(IndexCodes):
    try:
        print ('CsIndexCode', i, '/', len(IndexCodes))
        Constituent = pd.read_excel('e:/index/' + IndexCode + 'cons.xls', dtype=object )
        Constituent = Constituent[['指数代码Index Code', '成分券代码Constituent Code', '成分券名称Constituent Name', '成分券英文名称Constituent Name(Eng.)']]
        Constituent.columns = ['index_code', 'code', 'name', 'Ename']
        print ('CsIndex for ['+IndexCode+'] got.')
#        Constituents = Constituents.append(Constituent)
        Constituent.set_index('index_code')
        Constituent.to_sql('IndexConst', eng)

    except:
        pass

    if i>2:
        break


