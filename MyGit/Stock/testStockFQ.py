from sqlalchemy import create_engine
import data_fq  as fq
import pandas as pd
import concurrent.futures
import multiprocessing as mp


home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

engS = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')
engX = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxXdXr')
eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxIndexs')


StockLists = pd.read_sql('StockLists', engS).code.tolist()
d = pd.read_sql('000001', eng)[['datetime', 'close']]
d.datetime=d.datetime.str.replace('15:00', '')

StockCode = '002939'

bfq_data = pd.read_sql(StockCode, engS)
xdxr_data = pd.read_sql(StockCode, engX)



bfq_data.datetime=bfq_data.datetime.str.replace('15:00', '')
    
bfq_data.set_index('datetime', inplace=True)
bfq_data.index = pd.DatetimeIndex(bfq_data.index)

xdxr_data['datetime'] = xdxr_data['year'].map(str) + '-' + xdxr_data['month'].map(str)+ '-' + xdxr_data['day'].map(str)
xdxr_data.set_index('datetime', inplace=True)
xdxr_data.index = pd.DatetimeIndex(xdxr_data.index)

info = xdxr_data.query('category==1')
# info.to_csv('f:/info.csv')
bfq_data = bfq_data.assign(if_trade=1)

if len(info) > 0:
    data = pd.concat([bfq_data, info[['category' ,'fenhong', 'peigu', 'peigujia','songzhuangu']]] ,axis=1)
    data.dropna(thresh=10, axis=0, inplace=True)
    # data.to_csv('f:/dataRAW.csv')
    data['if_trade'].fillna(value=0, inplace=True)
    #data = data.fillna(method='ffill')
    #       data = pd.concat([data, info.loc[bfq_data.index[0]:bfq_data.index[-1], ['fenhong', 'peigu', 'peigujia',
#                                                                               'songzhuangu']]], axis=1)
else:
    # pass
    data = pd.concat([bfq_data, info[['category' ,'fenhong', 'peigu', 'peigujia','songzhuangu']]] ,axis=1)
data = data.fillna(0)
# data.to_csv('f:/ffill.csv')
data.close = data.close.astype('float32')
data.high = data.high.astype('float32')
data.low = data.low.astype('float32')
data.open = data.open.astype('float32')
data.vol = data.vol.astype('float32')

data['preclose'] = (data['close'].shift(1) * 10 - data['fenhong'] + data['peigu']
                    * data['peigujia']) / (10 + data['peigu'] + data['songzhuangu'])
# data.to_csv('f:/preclos.csv')
data['adj'] = (data['preclose'].shift(-1) /
                data['close']).fillna(1)[::-1].cumprod()
data = data.fillna(method='ffill')
data['open'] = (data['open'] * data['adj']).round(2)
data['high'] = (data['high'] * data['adj']).round(2)
data['low'] = (data['low'] * data['adj']).round(2)
data['close'] = (data['close'] * data['adj']).round(2)
data['preclose'] = data['preclose'] * data['adj']
data['volume'] = data['volume'] / \
    data['adj'] if 'volume' in data.columns else data['vol']/data['adj']
try:
    data['high_limit'] = data['high_limit'] * data['adj']
    data['low_limit'] = data['high_limit'] * data['adj']
except:
    pass

dd = data.query('if_trade==1').drop(['fenhong', 'peigu', 'peigujia', 'songzhuangu',
                                           'if_trade', 'category'], axis=1).query("open != 0")

# # def MultiStocksFQ(workers, jobs, d):
# #     with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
# #         for StockCode in jobs:
# #             result = pool.submit(StocksFq, StockCode)
# #             result.add_done_callback(Merg)



# # for i, StockCode in enumerate(StockLists):
# def StocksFq(StockCode):
#     # print('Index', i, '/', len(StockLists))
#     try:
#         Data = pd.read_sql(StockCode, engS)
#         # Data.to_csv('f:/'+StockCode+'.csv')
#         XdXr = pd.read_sql(StockCode, engX)
#         # XdXr.to_csv('f:/'+StockCode+'XdXr.csv')
#         a = fq.qfq(Data, XdXr)
#         a.reset_index('datetime', inplace=True)
#         a = a[['datetime', 'close']]
#         a.columns = ['datetime', StockCode]
        
#         print(StockCode, '融入数据集')
        
#     except:
#         pass
#     return a

# def Merg(res):
#     global d
#     res.reset_index(inplace=True)
#     d = d.set_index('datetime').join(res.set_index('datetime'))
#     d.reset_index(inplace=True)
#     return d


# for StockCode in StockLists:
#     res = StocksFq(StockCode)
#     p = Merg(res)


# # if __name__ == '__main__':

# #     p = MultiStocksFQ(6, StockLists, d)

# p.drop('close', axis=1,inplace=True)
# p.set_index('datetime', inplace=True)
# p = p.fillna(method='ffill')
# p.to_csv('g:\StocksOne.csv', encoding='utf8')
# # d.to_sql('StocksOne', eng, if_exists='replace')
# print('数据集融合完成')