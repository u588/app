from pyecharts import options as opts
from pyecharts.charts import Pie, Timeline
from pyecharts.faker import Faker

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/FindStocks')
data = pd.read_sql('FindStocks', eng).sort_values(by=['datetime'], ascending=False)
data = data.drop_duplicates(subset=['datetime', 'code'], keep='first')
def pie(date):
    d = data.groupby('datetime').get_group(date)
    dd = d[['name', 'code']]
    c = (
        Pie()
        .add(
            "",
            [list(z) for z in zip(dd.name, dd.code)],
            radius=["30%", "75%"],
            center=["50%", "60%"],
            rosetype="area",
        )
        .set_global_opts(title_opts=opts.TitleOpts(title=""))
    )
    return c













# attr = Faker.choose()
# tl = Timeline()
# for i in range(2015, 2020):
#     pie = (
#         Pie()
#         .add(
#             "商家A",
#             [list(z) for z in zip(attr, Faker.values())],
#             rosetype="radius",
#             radius=["30%", "55%"],
#         )
#         .set_global_opts(title_opts=opts.TitleOpts("某商店{}年营业额".format(i)))
#     )
#     tl.add(pie, "{}年".format(i))
# tl.render("timeline_pie.html")
