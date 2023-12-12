import pandas as pd
import numpy as np


a = pd.read_excel('g:/1/2/st000001.xlsx')
b = pd.read_excel('g:/1/2/st000001pcb5.xlsx')
c = pd.read_excel('g:/1/2/st000001pcb13.xlsx')


def CvCore(df):
    a = (df.mean()*df.std()).mean()
    return a

#pcb5取分析时间
i= 0
while i <= len(b):
    print(i)
    try:
        df = a[a.datetime>=b.loc[i][3:5][1]][a.datetime<=b.loc[i][3:5][0]].reset_index()[['open','close','high','low','mea']]
        b.loc[i,'Cv'] = CvCore(df)
        i = i + 1 
    except:
        i = i +1
        pass



