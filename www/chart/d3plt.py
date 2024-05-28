import pandas as pd
from sklearn import preprocessing
from sqlalchemy import create_engine


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockBas')

from bokeh.models import ColumnDataSource, RangeTool, WheelZoomTool
from bokeh.plotting import figure, show ,output_file
from bokeh.transform import log_cmap
from bokeh.layouts import column

def d3(CodeId):
    TOOLS="hover,crosshair,pan,box_zoom,undo,redo,reset,tap,save"

    TOOLTIPS = [
        ("Date", "@sdate"),
        ("Close", "@close"),
        ("Vol", "@vol"),
    ]

    df = pd.read_sql(CodeId, eng).reset_index(drop=True).reset_index()
    eng.dispose()
    StocksList = pd.read_sql('StocksDetail20236', engB)
    engB.dispose()
    St = StocksList.loc[StocksList['code']==CodeId]
    size =  ((preprocessing.minmax_scale(df.vol))*38).round(2)
    dates = pd.to_datetime(df.datetime.str[:10])
    sdate = df['datetime'].str[:10]
    source = ColumnDataSource(data=dict(date=dates, close=df.close, vol=df.vol, size=size, sdate=sdate))
    cmap = log_cmap(field_name='close', palette="RdYlGn8", low=min(df.close), high=max(df.close))

    p = figure(height=500, width=1800, tools=TOOLS, toolbar_location="right",
            x_axis_type="datetime", x_axis_location="above",
            background_fill_color="#efefef", x_range=(dates[len(dates)-500], dates[len(dates)-1]),
            tooltips = TOOLTIPS)

    # p.line('date', 'close', source=source)
    p.scatter(x='date', y='close', color=cmap, size='size', alpha=0.5,source=source,line_color='#333333')
    p.yaxis.axis_label = 'Price'

    select = figure(
                    height=100, width=1800, y_range=p.y_range,
                    x_axis_type="datetime", y_axis_type=None,
                    tools="", toolbar_location=None, background_fill_color="#efefef")

    range_tool = RangeTool(x_range=p.x_range)
    range_tool.overlay.fill_color = "navy"
    range_tool.overlay.fill_alpha = 0.2

    select.line('date', 'close', source=source)
    select.ygrid.grid_line_color = None
    select.add_tools(range_tool)
    wheel_zoom = WheelZoomTool()
    wheel_zoom.dimensions = 'width'
    p.add_tools(wheel_zoom)
    p.toolbar.active_scroll = wheel_zoom
    p.toolbar.autohide = True
    # output_file("/home/static/d3plt.html", title='D3 '+St.name.to_list()[0]+' : '+St.code.to_list()[0])
    c = column(p, select,sizing_mode="scale_both")
    return c