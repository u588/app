from pytdx.hq import TdxHq_API
import pandas as pd


api = TdxHq_API()
# if api.connect('119.147.212.81', 7709):
#     # ... same codes...
#     api.disconnect()

def GetIndex(category, market, code, start, count):
    # market(市场代码):深圳(0), 上海(1)
    #category(K线种类): 5分钟K线(0), 1分钟K线(8), 日K线(9)
    #start(开始位置): 整数型偏移量
    #count(请求K线数目): 最大800的整数型
    data = api.to_df(api.get_index_bars(category, market, code, start, count)) # 返回DataFrame
    return(data)


def GetStock(category, market, code, start, count):
    # market(市场代码):深圳(0), 上海(1)
    #category(K线种类): 5分钟K线(0), 1分钟K线(8), 日K线(9)
    #start(开始位置): 整数型偏移量
    #count(请求K线数目): 最大800的整数型
    data = api.to_df(api.get_security_bars(category, market, code, start, count)) # 返回DataFrame
    return(data)

