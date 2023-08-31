import pandas as pd
from sklearn import preprocessing
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

from bokeh.models import ColumnDataSource, RangeTool, WheelZoomTool
from bokeh.plotting import figure, show ,output_file
from bokeh.transform import log_cmap
from bokeh.layouts import column

TOOLS="hover,crosshair,pan,box_zoom,undo,redo,reset,tap,save"


TOOLTIPS = [
    ("Date", "@sdate"),
    ("Close", "@close"),
    ("Vol", "@vol"),
]

df = pd.read_sql('600996', eng).reset_index(drop=True).reset_index()
size =  ((preprocessing.minmax_scale(df.vol))*38).round(2)
dates = pd.to_datetime(df.datetime.str[:10])
sdate = df['datetime'].str[:10]
source = ColumnDataSource(data=dict(date=dates, close=df.close, vol=df.vol, size=size, sdate=sdate))
cmap = log_cmap(field_name='close', palette="RdYlGn8", low=min(df.close), high=max(df.close))

p = figure(height=600, width=1400, tools=TOOLS, toolbar_location="right",
           x_axis_type="datetime", x_axis_location="above",
           background_fill_color="#efefef", x_range=(dates[len(dates)-500], dates[len(dates)-1]),
           tooltips = TOOLTIPS)

# p.line('date', 'close', source=source)
p.scatter(x='date', y='close', color=cmap, size='size', alpha=0.5,source=source,line_color='#333333')
p.yaxis.axis_label = 'Price'

select = figure(
                height=100, width=1400, y_range=p.y_range,
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
output_file("stocks.html", title="stocks.py example")
show(column(p, select))



import numpy as np

from bokeh.models import WheelZoomTool
from bokeh.plotting import figure, show

x = np.random.random(size=200)
y = np.random.random(size=200)

# Basic plot setup
p = figure(width=400, height=400, title='Select and Zoom',
              tools="hover,crosshair,pan,box_zoom,undo,redo,reset,tap,save")


wheel_zoom = WheelZoomTool()
wheel_zoom.dimensions = 'width'
p.add_tools(wheel_zoom)
p.toolbar.active_scroll = wheel_zoom

p.circle(x, y, size=5)
show(p)
# select_overlay = plot.select_one(WheelZoomTool).overlay

# select_overlay.fill_color = "firebrick"
# select_overlay.line_color = None

# zoom_overlay = plot.select_one(WheelZoomTool).overlay

# zoom_overlay.line_color = "olive"
# zoom_overlay.line_width = 8
# zoom_overlay.line_dash = "solid"
# zoom_overlay.fill_color = None

# plot.select_one(WheelZoomTool).overlay.line_dash = [10, 10]
WheelZoomTool
show(plot)