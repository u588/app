import datetime
import backtrader as bt
from backtrader_plotting import Bokeh
from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

class TestStrategy(bt.Strategy):
    params = (
        ('buydate', 21),
        ('holdtime', 6),
    )

    def next(self):
        if len(self.data) == self.p.buydate:
            self.buy(self.datas[0], size=None)

        if len(self.data) == self.p.buydate + self.p.holdtime:
            self.sell(self.datas[0], size=None)


if __name__ == '__main__':
    cerebro = bt.Cerebro()

    cerebro.addstrategy(TestStrategy, buydate=3)
    df = pd.read_sql('000001', eng)
    df['datetime']=pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    cerebro.run()

    b = Bokeh(style='bar', plot_mode='single')
    cerebro.plot(b)