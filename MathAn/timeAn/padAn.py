import pandas as pd

a = pd.read_excel('g:/1/2/st000001.xlsx')
b = pd.read_excel('g:/1/2/st000001pcb5.xlsx')
c = pd.read_excel('g:/1/2/st000001pcb13.xlsx')

a[a.datetime>=b.loc[1][2:5][1]][a.datetime<=b.loc[1][2:5][0]].reset_index().amount