import pandas as pd


tdx88 = pd.read_excel('G:/Gitee/App/Data/2023TdxCs/csIndex2023.xlsx', dtype={'IndexCode':object})
tdxRaw = pd.read_excel('G:/Gitee/App/Data/20230617/TDXIndexsOK2023.xlsx', dtype={'IndexCode':object})

tdxB = pd.read_excel('G:/Gitee/App/Data/2023TdxCs/tdxBolckIndexs2023.xlsx', dtype={'IndexCode':object, })


tdxsz = pd.read_excel('G:/Gitee/App/Data/TDXdata/New/szIndexs.xlsx', dtype={'IndexCode':object})
cs = pd.read_excel('G:/Gitee/App/Data/CSdata/csIndex2023.xlsx', dtype={'IndexCode':object})
tdx = pd.read_excel('G:/Gitee/App/Data/2023TdxCs/tdxRaw-blkmerged.xlsx', dtype={'IndexCode':object})

tdx.drop_duplicates(subset='IndexCode', keep='first', inplace=True)

m1 = pd.merge(tdxRaw, tdx88, on='IndexCode', how='outer')
m1['Num'] = m1.Num_x.fillna(m1.Num_y)
m1['IndexSTL'] = m1.IndexSTL_x.fillna(m1.IndexSTL_y)
m1['From'] = m1.From_x.fillna(m1.From_y)
m1[''] = m1.Num_x.fillna(m1.Num_y)
m1.to_excel('g:/gitee/20230617/810merged.xlsx')

#NaN值处理

tdx['Num'] = tdx.Num_x.fillna(tdx.Num_y)
