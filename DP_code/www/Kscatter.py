import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Scatter
from sklearn import preprocessing

from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

CodeId = '600281'
data= pd.read_sql(CodeId, eng).tail(30)
data.rename(columns={'vol':'volume','datetime':'date'}, inplace=True)
data.date = data.date.str.replace(' 15:00','')

c = (
    Scatter()
    .add_xaxis(xaxis_data=data.date.tolist())
    .add_yaxis(
               series_name="",
               y_axis=data.close.tolist(),
               symbol_size=(((preprocessing.minmax_scale(data.volume)*25).round(0))).tolist(),
               label_opts=opts.LabelOpts(is_show=False),
               )
    .render("f:/tmp/scatter.html")
)