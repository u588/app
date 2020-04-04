import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

"""
    规格化后的数据显示
"""
# 股指成分股
Index = '399997'
files = 'f:/StocksSet/I' + Index +'NormConstPct.csv'

#==========

# # #指数
# IDay1 = '2018-09-12'
# files ='f:/IndexsSet/I' + IDay1 +'NormPct.csv'
# # #==========


DataSet = pd.read_csv(files)
DataSet['date'] = pd.to_datetime(DataSet['date'])
DataSet.set_index('date', inplace=True)


#sns.set(context="paper", style="whitegrid", palette="deep", font="sans-serif", font_scale=1, color_codes=True, rc=None)
Datas = DataSet[['002304', '603369', '000568','000860','603589','000858']]

#双变量散点图 大数据量用kind='hex'
#sns.jointplot(x=DataSet['600438'], y=DataSet['002714'],kind='hex', data=DataSet)
# sns.pairplot(DataSet)
# DataSet.columns
# DataSet.reset_index(inplace=True)
# g = sns.FacetGrid(DataSet, col='600438', col_order=DataSet.columns, height= 1.7, aspect=4,)
# g.map(sns.lineplot(data=Datas))

#sns.palplot(sns.color_palette('hls', 12))
# sns.palplot(sns.color_palette('Paired',10))
# sns.distplot(DataSet['600438'], kde=True)


#sns.lineplot(data=Datas,dashes=True,sort=True, palette='tab20')
# sns.factorplot()
Datas.plot(kind='density', grid=True, figsize=(18, 8), colormap='tab10' , sort_columns=True, linewidth=2 )
plt.show()