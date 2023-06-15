import pandas as pd

tdxB = pd.read_excel('G:/Gitee/App/Data/TDXdata/New/tdxBolckIndexs2023.xlsx', dtype={'IndexCode':object})
tdxzz = pd.read_excel('G:/Gitee/App/Data/TDXdata/New/zzIndexs.xlsx', dtype={'IndexCode':object})
tdxsh = pd.read_excel('G:/Gitee/App/Data/TDXdata/New/shIndexs.xlsx', dtype={'IndexCode':object})
tdxsz = pd.read_excel('G:/Gitee/App/Data/TDXdata/New/szIndexs.xlsx', dtype={'IndexCode':object})
cs = pd.read_excel('G:/Gitee/App/Data/CSdata/csIndex2023.xlsx', dtype={'IndexCode':object})
tdx = pd.read_excel('G:/Gitee/App/Data/TDXdata/New/tdxtext.xlsx', dtype={'IndexCode':object})

tdx.drop_duplicates(subset='IndexCode', keep='first', inplace=True)

m1 = pd.merge(tdx, cs, on='IndexCode', how='outer')