import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import pandas as pd

mpl.rcParams['font.sans-serif'] = ['KaiTi'] # 指定默认字体
mpl.rcParams['axes.unicode_minus'] = False # 解决保存图像是负号'-'显示为方块的问题

plt.style.use({'figure.figsize':(12, 6)})
# sns.set(context="notebook", style="whitegrid", palette="deep", font="KaiTi", font_scale=1, color_codes=True, rc=None)
"""
    规格化后精选指数图示
"""
# 股指成分股
days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']


Day = '2018-02-12'

file = 'Point'
file = 'Down'
# file = 'Up'
files = ''
if file =='Norm':
    files = ''
else:
    files = 'Point'

#读取上证指数
shIndex= pd.read_csv('f:/IndexsSet/I' + Day + files + 'Norm.csv')[['datetime', '000001']]
shIndex.set_index('datetime', inplace=True)
shIndex.rename(columns={'000001':'000001上证指数'}, inplace=True)
shIndex.index = pd.DatetimeIndex(shIndex.index)

#读取规格化指数数据集
# Day = Day[:4]+Day[5:7]+Day[8:]


DataSet = pd.read_csv('f:/StocksSet/S' + Day + file + 'Norm.csv')
DataSet['date'] = pd.to_datetime(DataSet['date'])
DataSet.set_index('date', inplace=True)
DataSet = shIndex.join(DataSet)

#读取需要比对的指数集,代码与名称合并
ConstsUp = pd.read_csv('f:/StocksSet/S' + Day +file + 'Up.csv', dtype={'code':object})[['code', 'name']]
ConstsUp['const_code'] = ConstsUp['code'] + ConstsUp['name']

ConstsDown = pd.read_csv('f:/StocksSet/S' + Day +file + 'Down.csv', dtype={'code':object})[['code', 'name']]
ConstsDown['const_code'] = ConstsDown['code'] + ConstsDown['name']

UpLists = ConstsUp['code'].tolist()
# try:
#     UpLists.remove('000001')
# except:
#     pass

UpNames = ConstsUp['const_code'].tolist()
# try:
#     UpNames.remove('000001上证指数')
# except:
#     pass
UpSet = DataSet[['000001上证指数']+UpLists[:6]]
UpSet.columns = ['000001上证指数']+UpNames[:6]


DownLists = ConstsDown['code'].tolist()
# try:
#     DownLists.remove('000001')
# except:
#     pass

DownNames = ConstsDown['const_code'].tolist()
# try:
#     DownNames.remove('000001上证指数')
# except:
#     pass
DownSet = DataSet[['000001上证指数']+DownLists[:6]]
DownSet.columns = ['000001上证指数']+DownNames[:6]
 

MergSet = pd.merge(UpSet, DownSet, left_index=True, on='000001上证指数')

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


MergSet.plot(title=Day+file+'Merge', kind='line', style='-', grid=True, figsize=(18, 9), colormap='gist_rainbow' , sort_columns=True, linewidth=0.8 )
plt.subplots_adjust(left=0.03 ,bottom=0.12,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
plt.savefig('f:/StocksPlot/S'+Day +files + file+'Merg.png', dpi=350)

UpSet.plot(title=Day+file+'绩优股', kind='line', style='-', grid=True, figsize=(12, 6), colormap='gist_rainbow' , sort_columns=True, linewidth=1.1 )
plt.subplots_adjust(left=0.03 ,bottom=0.12,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
plt.savefig('f:/StocksPlot/S'+ Day +files+ file +'Up.png', dpi=350)
#plt.xlabel('UpSet')
# sns.lineplot(data=UpSet,dashes=False, sort=True, palette='gist_rainbow', linewidth=1.1)
# plt.xlabel('UpSet')
# # plt.figure()
DownSet.plot(title=Day+file+'绩差股', kind='line', style='-', grid=True, figsize=(12, 6), colormap='rainbow' , sort_columns=True, linewidth=1.1 )
plt.subplots_adjust(left=0.03 ,bottom=0.12,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
plt.savefig('f:/StocksPlot/S'+ Day +files+ file +'Down.png', dpi=350)
#plt.xlabel('DownSet')
# sns.lineplot(data=DownSet, dashes=False, sort=True, palette='rainbow', linewidth=1.1)
# plt.xlabel('DownSet')

# sns.factorplot()

UpSet.plot(subplots=True, title=Day+file+'绩优股', kind='density', grid=True, figsize=(8, 3.8), colormap='gist_rainbow' , sort_columns=True, linewidth=1.5 )
plt.savefig('f:/StocksPlot/S' + Day +files + file+'UpKde.png')

DownSet.plot(subplots=True, title=Day+file+'绩差股', kind='kde', grid=True, figsize=(8, 3.8), colormap='rainbow' , sort_columns=True, linewidth=1.5 )
plt.savefig('f:/StocksPlot/S'+ Day +files+ file +'DownKde.png')
plt.show()

# DownSet.plot(subplots=True, title=day+'绩差', kind='kde', grid=True, figsize=(8, 3.8), colormap='rainbow' , sort_columns=True, linewidth=1.5 )
# plt.savefig('f:/IndexsPlot/I'+ day +files +'DownKde.png')
# plt.show()

# sns.lineplot(data=shIndex, style='-', linewidth=2)
# sns.lineplot(data=UpSet, dashes=True, sort=True, palette='gist_rainbow', linewidth=1)
# plt.xlabel('UpSet')
# plt.figure()

# sns.lineplot(data=shIndex, style='-', linewidth=2)
# sns.lineplot(data=DownSet, dashes=False, sort=True, palette='gist_rainbow', linewidth=1)
# plt.xlabel('DownSet')

# # sns.factorplot()

# UpSet.plot(subplots=True, kind='density', grid=True, figsize=(12, 6), colormap='gist_rainbow' , sort_columns=True, linewidth=2 )
# plt.xlabel('UpSet')


# DownSet.plot(subplots=True, kind='density', grid=True, figsize=(12, 6), colormap='gist_rainbow' , sort_columns=True, linewidth=2 )
# plt.xlabel('DownSet')
# plt.show()
