from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')
IndexLists = pd.read_sql('csIndexs', eng).Index_code.to_list()

D = pd.DataFrame(columns=['Index_code', 'Index_name','3D','5D','21D','55D']).astype(dtype={'3D':float,'5D':float,'21D':float,'55D':float})
for codeID in IndexLists:
    try:
        Data = pd.read_sql(codeID, eng)
        d = Data.head(1)[['Index_code', 'Index_name']]
        d['3D'] = Data['PCB'].tail(3).sum().round(2)
        d['5D'] = Data['PCB'].tail(5).sum().round(2)
        d['21D'] = Data['PCB'].tail(21).sum().round(2)
        d['55D'] = Data['PCB'].tail(55).sum().round(2)
        # d.reset_index(drop=True, inplace =True)

        D = D.append(d)
        # print(codeID + 'Append !')
    except:
        pass
D.set_index('Index_code').to_sql('csIndexsData', eng, if_exists = 'replace')