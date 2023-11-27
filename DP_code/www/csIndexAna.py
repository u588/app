from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')
IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()


def getIndexs(Code):
    D = pd.DataFrame(columns=['Index_code', 'Index_name','PCB']).astype(dtype={'PCB':float})
    for codeID in IndexLists:
        try:
            Data = pd.read_sql(codeID, eng).tail(int(Code))
            d = Data.head(1)[['Index_code', 'Index_name']]
            d['PCB'] = Data['PCB'].sum().round(2)
            d.reset_index(drop=True, inplace =True)

            D = D.append(d)
            # print(codeID + 'Append !')
        except:
            pass
    return D
# dd = getIndexs(28).sort_values('PCB').head(10).reset_index(drop=True)
#  ddd.loc[ddd['Index_code']=='930901'].reset_index(drop=True)
eng.dispose()