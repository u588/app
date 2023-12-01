import backtrader as bt
import pandas as pd
from datetime import datetime
from backtrader_plotting import Bokeh
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')



def get_feeds(code):
    df = pd.read_sql(code, eng)
    df['datetime']=pd.to_datetime(df['datetime'])   
    start_date = datetime(2022,7,30,15,00,00)  # 回测开始时间
    end_date = datetime(2023,11,30,15,00,00)  # 回测结束时间
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

c = bt.Cerebro()
b = c.adddata(get_feeds('000001'))
b.