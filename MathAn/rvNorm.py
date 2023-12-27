import pandas as pd
import numpy as np

def rvNorm(data):
    x = pd.DataFrame(columns=['datetime','x','y'])
    df = data.drop('datetime', axis=1)
    df = ((df.T-df.T.min())/(df.T.max()-df.T.min())).T
    n = len(df)
    m = df.shape[1]
    s = np.array([(np.cos(t), np.sin(t))
                  for t in [2.0 * np.pi * (i / float(m))
                            for i in range(m)]])
    for i in range(n):
        row = df.iloc[i].values
        row_ = np.repeat(np.expand_dims(row, axis=1), 2, axis=1)
        y = (s * row_).sum(axis=0) / row.sum()
        x.loc[i, 'x'] = y[0]
        x.loc[i,'y'] = y[1]
        x.loc[i,'datetime'] = data.loc[i,'datetime']
    return x