from pyecharts import options as opts
from pyecharts.charts import Pie
import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg://sa:11111111@10.145.254.56:5432/tdxIndex')

def pie(date):
    d = pd.read_sql('tdxIndexsData', eng)
    # data = d.sort_values(by=date).head(10).append(d.sort_values(by=date).tail(10))[['Index_code','Index_name', date]].reset_index(drop=True)
    data = pd.concat([d.sort_values(by=date).head(10), d.sort_values(by=date).tail(10)[['IndexCode','IndexName', date]].reset_index(drop=True)])

    dd = data[['IndexName', date]]
    c = (
        Pie()
        .add(
            "",
            [list(z) for z in zip(dd['IndexName'], dd[date])],
            radius=["30%", "75%"],
            center=["50%", "60%"],
            rosetype="area",
        )
        .set_global_opts(title_opts=opts.TitleOpts(title=""))
    )
    return c