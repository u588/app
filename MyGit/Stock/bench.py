




instruments = ['000009.SZA']
start_date = '2014-09-16'# 起始时间    
end_date = '2017-01-03' # 结束时间


def initialize(context):
   
    context.set_commission(PerDollar(0.0015)) # 手续费设置
    # 需要设置计算MACD的相关参数参数
    context.short = 12
    context.long = 26
    context.smoothperiod = 9
    context.observation = 100
   
   
def handle_data(context, data):
 
    if context.trading_day_index < 100: # 在100个交易日以后才开始真正运行 
        return
    
    sid = context.symbol(instruments[0])
    # 获取价格数据
    prices = data.history(sid, 'price', context.observation, '1d')
    # 用Talib计算MACD取值，得到三个时间序列数组，分别为macd, signal 和 hist
    macd, signal, hist = talib.MACD(np.array(prices), context.short,
                                    context.long, context.smoothperiod)
 
    # 计算现在portfolio中股票的仓位
    cur_position = context.portfolio.positions[sid].amount
    
    # 策略逻辑
    # 卖出逻辑 macd下穿signal
    if macd[-1] - signal[-1] < 0 and macd[-2] - signal[-2] > 0:
        # 进行清仓
        if cur_position > 0 and data.can_trade(sid):
            context.order_target_value(sid, 0)

    # 买入逻辑  macd上穿signal
    if macd[-1] - signal[-1] > 0 and macd[-2] - signal[-2] < 0:
        # 买入股票
        if cur_position == 0 and data.can_trade(sid):
            context.order_target_percent(sid, 1)

m=M.backtest.v5( 
    instruments=instruments,
    start_date=start_date,
    end_date=end_date,
    initialize=initialize,
    handle_data=handle_data,
    order_price_field='close',
    order_price_field_buy='open',
    order_price_field_sell='open',
    capital_base=float("1.0e6"),
    benchmark='000300.INDX',
)