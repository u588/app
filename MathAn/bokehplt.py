import pandas as pd
from sklearn import preprocessing
from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, show ,output_file
from bokeh.transform import linear_cmap,log_cmap

TOOLS="hover,crosshair,pan,wheel_zoom,box_zoom,undo,redo,reset,tap,save"


TOOLTIPS = [
    ("Date", "@i"),
    ("Close", "@y"),
    ("Vol", "@j"),
]

df = pd.read_sql('600584', eng).reset_index(drop=True).reset_index()
x = df['index']

y = df.close
size =  ((preprocessing.minmax_scale(df.vol))*38).round(2)
date = df['datetime'].str[:10]
vol = df['vol']
source = ColumnDataSource(dict(x=x,y=y,z=size,i=date,j=vol))

cmap = log_cmap(field_name='y', palette="Inferno256", low=min(y), high=max(y))

p = figure(width=2100, height=600, title="Linear color map based on Y",tools=TOOLS, tooltips = TOOLTIPS)
p.scatter(x='x', y='y', color=cmap, size='z', alpha=0.5,source=source,line_color='#333333')
p.line(df['index'], df.close, line_width=1, alpha=0.3)

p.toolbar.autohide = True

output_file("stocks.html", title="stocks.py example")
show(p)
