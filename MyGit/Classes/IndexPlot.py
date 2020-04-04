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
days =['2001-06-14', '2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']

#读取规格化指数数据集
day = '2018-02-12'

file = 'Point'

if file =='Norm':
    files = ''
else:
    files = 'Point'

DataSet = pd.read_csv('f:/IndexsSet/I' + day + files + 'Norm.csv')
DataSet['datetime'] = pd.to_datetime(DataSet['datetime'])
DataSet.set_index('datetime', inplace=True)

#读取需要比对的指数集,代码与名称合并
IndexSetUp = pd.read_csv('f:/IndexsSet/I' + day +files + 'Up.csv', dtype={'index_code':object})[['index_code', 'index_name']]
IndexSetUp['code'] = IndexSetUp['index_code'] + IndexSetUp['index_name']

IndexSetDown = pd.read_csv('f:/IndexsSet/I' + day +files +'Down.csv', dtype={'index_code':object})[['index_code', 'index_name']]
IndexSetDown['code'] = IndexSetDown['index_code'] + IndexSetDown['index_name']

UpLists = IndexSetUp['index_code'].tolist()
try:
    UpLists.remove('000001')
except:
    pass

UpNames = IndexSetUp['code'].tolist()
try:
    UpNames.remove('000001上证指数')
except:
    pass
UpSet = DataSet[(['000001'] + UpLists)[:8]]
UpSet.columns = (['000001上证指数'] + UpNames)[:8]

DownLists = IndexSetDown['index_code'].tolist()
try:
    DownLists.remove('000001')
except:
    pass

DownNames = IndexSetDown['code'].tolist()
try:
    DownNames.remove('000001上证指数')
except:
    pass
DownSet = DataSet[(['000001'] + DownLists)[:6]]
DownSet.columns = (['000001上证指数']+ DownNames)[:6]

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

MergSet.plot(title=day+'Merge', kind='line', style='-', grid=True, figsize=(18, 9), colormap='gist_rainbow' , sort_columns=True, linewidth=0.8 )
plt.subplots_adjust(left=0.03 ,bottom=0.12,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
plt.savefig('f:/IndexsPlot/I'+day +files +'Merg.png', dpi=350)

UpSet.plot(title=day+'绩优', kind='line', style='-', grid=True, figsize=(12, 6), colormap='gist_rainbow' , sort_columns=True, linewidth=1.1 )
plt.subplots_adjust(left=0.03 ,bottom=0.12,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
plt.savefig('f:/IndexsPlot/I'+ day +files +'Up.png', dpi=350)
#plt.xlabel('UpSet')
# sns.lineplot(data=UpSet,dashes=False, sort=True, palette='gist_rainbow', linewidth=1.1)
# plt.xlabel('UpSet')
# # plt.figure()
DownSet.plot(title=day+'绩差', kind='line', style='-', grid=True, figsize=(12, 6), colormap='rainbow' , sort_columns=True, linewidth=1.1 )
plt.subplots_adjust(left=0.03 ,bottom=0.12,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
plt.savefig('f:/IndexsPlot/I'+ day +files +'Down.png', dpi=350)
#plt.xlabel('DownSet')
# sns.lineplot(data=DownSet, dashes=False, sort=True, palette='rainbow', linewidth=1.1)
# plt.xlabel('DownSet')

# sns.factorplot()

UpSet.plot(subplots=True, title=day+'绩优', kind='density', grid=True, figsize=(8, 3.8), colormap='gist_rainbow' , sort_columns=True, linewidth=1.5 )
plt.savefig('f:/IndexsPlot/I' + day +files +'UpKde.png')


DownSet.plot(subplots=True, title=day+'绩差', kind='kde', grid=True, figsize=(8, 3.8), colormap='rainbow' , sort_columns=True, linewidth=1.5 )
plt.savefig('f:/IndexsPlot/I'+ day +files +'DownKde.png')
plt.show()