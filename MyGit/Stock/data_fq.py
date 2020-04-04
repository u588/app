
# coding:utf-8
import datetime
import pandas as pd


def qfq(bfq_data, xdxr_data):
    '使用数据库数据进行复权'

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
    return data.query('if_trade==1').drop(['fenhong', 'peigu', 'peigujia', 'songzhuangu',
                                           'if_trade', 'category'], axis=1).query("open != 0")


def hfq(bfq_data, xdxr_data):
    '使用数据库数据进行复权'

    bfq_data.datetime=bfq_data.datetime.str.replace('15:00', '')
    
    bfq_data.set_index('datetime', inplace=True)
    bfq_data.index = pd.DatetimeIndex(bfq_data.index)

    xdxr_data['datetime'] = xdxr_data['year'].map(str) + '-' + xdxr_data['month'].map(str)+ '-' + xdxr_data['day'].map(str)
    xdxr_data.set_index('datetime', inplace=True)
    xdxr_data.index = pd.DatetimeIndex(xdxr_data.index)

    info = xdxr_data.query('category==1')
    bfq_data = bfq_data.assign(if_trade=1)

    if len(info) > 0:
        data = pd.concat([bfq_data, info[['category' ,'fenhong', 'peigu', 'peigujia','songzhuangu']]] ,axis=1)
        data.dropna(thresh=10, axis=0, inplace=True)
        data['if_trade'].fillna(value=0, inplace=True)

    else:
        data = pd.concat([bfq_data, info[['category' ,'fenhong', 'peigu', 'peigujia','songzhuangu']]] ,axis=1)
    data = data.fillna(0)
    data['preclose'] = (data['close'].shift(1) * 10 - data['fenhong'] + data['peigu']
                        * data['peigujia']) / (10 + data['peigu'] + data['songzhuangu'])
    data['adj'] = (data['close'] / data['preclose'].shift(-1)
                   ).cumprod().shift(1).fillna(1)
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
    return data.query('if_trade==1').drop(['fenhong', 'peigu', 'peigujia', 'songzhuangu'], axis=1).query("open != 0")
