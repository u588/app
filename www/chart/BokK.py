import pandas as pd
from sklearn import preprocessing
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')

from bokeh.models import ColumnDataSource, RangeTool, WheelZoomTool
from bokeh.plotting import figure
from bokeh.layouts import gridplot
from bokeh.transform import log_cmap
from bokeh.layouts import column
from math import pi

def K (Code):
    df = pd.read_sql(Code, eng).reset_index(drop=True).reset_index().tail(500)
    eng.dispose()
    StocksList = pd.read_sql('StocksDetail20236', engB)
    engB.dispose()

    StName = StocksList.loc[StocksList['code']==Code]['name']    
    df['date'] = pd.to_datetime(df['datetime'])
    inc = df.close > df.open
    dec = df.open > df.close
    w = 12*60*60*1000
    TOOLS = "pan,wheel_zoom,box_zoom,reset,save"

    p = figure(x_axis_type="datetime", tools=TOOLS, plot_width=1200, plot_height=500, title = Code)
    p.xaxis.major_label_orientation = pi/4
    p.grid.grid_line_alpha=0.2

    p.segment(df.date, df.high, df.date, df.low, color="black")
    p.vbar(df.date[inc], w, df.open[inc], df.close[inc], fill_color="#D5E1DD", line_color="black")
    p.vbar(df.date[dec], w, df.open[dec], df.close[dec], fill_color="#F2583E", line_color="black")

    p2 = figure(x_axis_type="datetime", tools="", toolbar_location=None, plot_width=1200, plot_height=200, x_range=p.x_range)
    p2.xaxis.major_label_orientation = pi/4
    p2.grid.grid_line_alpha=0.2
    p2.vbar(df.date, w, df.vol, [0]*df.shape[0])


    c = column(p,p2)

    return c   

