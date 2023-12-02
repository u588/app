import backtrader as bt
import pandas as pd
from datetime import datetime
from backtrader_plotting import Bokeh
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

def get_feeds(code,start_date,end_date):
    df = pd.read_sql(code, eng)
    eng.dispose()
    df['datetime']=pd.to_datetime(df['datetime'])   
    # start_date = datetime(2022,7,30,15,00,00)  # 回测开始时间
    # end_date = datetime(2023,11,30,15,00,00)  # 回测结束时间
    feeds = bt.feeds.PandasData(
        name = code,
        dataname= df,
        datetime=0,
        open=1,
        high=3,
        low=4,
        close=2,
        volume=5,
        openinterest=-1,
        fromdate=start_date,
        todate=end_date
    )
    return feeds

# Create a Stratey
class TestStrategy(bt.Strategy):
    params = (
        ('maperiod', 15),
    )
 
    def log(self, txt, dt=None):
        ''' 记录'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))
 
    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close
 
        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None
 
        # 增加移动平均指标
        self.sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.maperiod)
 
        # 增加划线的指标
        bt.indicators.ExponentialMovingAverage(self.datas[0], period=25)
        bt.indicators.WeightedMovingAverage(self.datas[0], period=25,
                                            subplot=True)
        bt.indicators.StochasticSlow(self.datas[0])
        bt.indicators.MACDHisto(self.datas[0])
        rsi = bt.indicators.RSI(self.datas[0])
        bt.indicators.SmoothedMovingAverage(rsi, period=10)
        bt.indicators.ATR(self.datas[0], plot=False)
 
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return
 
        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))
 
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))
 
            self.bar_executed = len(self)
 
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
 
        # Write down: no pending order
        self.order = None
 
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
 
        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))
 
    def next(self):
        # Simply log the closing price of the series from the reference
        self.log('Close, %.2f' % self.dataclose[0])
 
        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return
 
        # Check if we are in the market
        if not self.position:
 
            # Not yet ... we MIGHT BUY if ...
            if self.dataclose[0] > self.sma[0]:
 
                # BUY, BUY, BUY!!! (with all possible default parameters)
                self.log('BUY CREATE, %.2f' % self.dataclose[0])
 
                # Keep track of the created order to avoid a 2nd order
                self.order = self.buy()
 
        else:
 
            if self.dataclose[0] < self.sma[0]:
                # SELL, SELL, SELL!!! (with all possible default parameters)
                self.log('SELL CREATE, %.2f' % self.dataclose[0])
 
                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()
 
if __name__ == '__main__':
    cerebro = bt.Cerebro(optreturn=False)
    
    # 增加多参数的策略
    strats = cerebro.optstrategy(
        TestStrategy,
        maperiod=range(10, 31))
    
    #获取数据
    # df = pd.read_sql('600000', eng)
    # df['datetime']=pd.to_datetime(df['datetime'])
    # df['date']=df['datetime']
    # df = df.set_index('date')  
    # new=['open','high','low','close','vol']
    # df = df.reindex(columns=new)  
    # stock_hfq_df = df
    startDay = datetime(2023,7,30,15,00,00)  # 回测开始时间
    endDay = datetime(2023,12,2,15,00,00)  # 回测结束时间
    # data = bt.feeds.PandasData(dataname=stock_hfq_df, fromdate=start_date, todate=end_date,)  # 加载数据
    cerebro.adddata(get_feeds('000001',startDay,endDay))  # 将数据传入回测系统
       
    cerebro.broker.setcash(100000.0)
    # Set the commission - 0.1% ... divide by 100 to remove the %
    cerebro.broker.setcommission(commission=0)
     # Add a FixedSize sizer according to the stake 每次买卖的股数量
    cerebro.addsizer(bt.sizers.FixedSize, stake=70)
 
 
 
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
 
    cerebro.run()
 
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    
    b = Bokeh(style='bar', plot_mode='single')
    cerebro.plot(b)