import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt


from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

df = pd.read_sql('600188', eng).tail(100).reset_index(drop=True).reset_index()

#时间转换
df['data'] = pd.to_datetime(df.datetime).dt.strftime('%Y%m%d')
x = df['index']
y = df.close
z = df.vol
fig = plt.figure()
ax = fig.add_axes(rect=(0, 0.05, 0.95, 0.95), projection='3d')

ax.scatter()
ax.plot_surface(x, y, z, rstride=1, cstride=1, cmap='RdBu_r', vmin=-0.5, vmax=0.5)
ax.set_xlabel('X')
ax.set_ylabel('Y')
# ax.set_xticks(np.arange(-1, 1.1, 0.5))
# ax.set_yticks(np.arange(-1, 1.1, 0.5))
ax.set_zlabel('Z')
plt.show()


