import pandas as pd
import numpy as np

df = pd.read_excel('g:/tdxFS/1.xlsx').T.drop_duplicates().T
ls = pd.read_excel('g:/tdxFS/tdxFSLisRAW.xlsx').set_index('Code').T

dfa = df.replace(0, np.nan).dropna(axis=1, thresh=1)
la = ls[list(set(ls.columns.values)&set(dfa.columns.values))].T.sort_values(by='Index').reset_index()
la['Num'] = 1
dfb = df.replace(0, np.nan).dropna(axis=1, thresh=100)
lb = ls[list(set(set(dfb.columns.values)&set(ls.columns.values)))].T.sort_values(by='Index').reset_index()
lb['Num'] = 100
dfc = df.replace(0, np.nan).dropna(axis=1, thresh=500)
lc = ls[list(set(set(dfc.columns.values)&set(ls.columns.values)))].T.sort_values(by='Index').reset_index()
lc['Num'] = 500
dfd = df.replace(0, np.nan).dropna(axis=1, thresh=2000)
ld = ls[list(set(set(dfd.columns.values)&set(ls.columns.values)))].T.sort_values(by='Index').reset_index()
ld['Num'] = 2000

a = pd.read_excel('g:/tdxFS/out.xlsx')
pd.merge(a,lc, on ='cnName', how='outer').to_excel('g:/tdxfs/out1.xlsx')

