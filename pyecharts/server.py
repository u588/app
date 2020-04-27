from flask import Flask
from jinja2 import Markup, Environment, FileSystemLoader
from pyecharts.globals import CurrentConfig

# 关于 CurrentConfig，可参考 [基本使用-全局变量]
CurrentConfig.GLOBAL_ENV = Environment(loader=FileSystemLoader("./templates"))

from pyecharts import options as opts
from pyecharts.charts import Kline
from pyecharts.charts import Bar
import tushare as ts
import pandas as pd
import numpy as np


app = Flask(__name__, static_folder="templates")


def bar_base() -> Bar:
    c = (
        Bar()
        .add_xaxis(["衬衫", "羊毛衫", "雪纺衫", "裤子", "高跟鞋", "袜子"])
        .add_yaxis("商家A", [5, 20, 36, 10, 75, 90])
        .add_yaxis("商家B", [15, 25, 16, 55, 48, 8])
        .set_global_opts(title_opts=opts.TitleOpts(title="Bar-基本示例", subtitle="我是副标题"))
    )
    return c

def Kline_zoom() -> Kline:
    d = ts.get_hist_data('000893')[['open', 'close','low','high' ]].head(100).sort_index(ascending=True)
    x = d.index.tolist()
    data = np.array(d).tolist()
    c = (
        Kline()
        .add_xaxis(x)
        .add_yaxis("kline", data)
        .set_global_opts(
            xaxis_opts=opts.AxisOpts(is_scale=True),
            yaxis_opts=opts.AxisOpts(
                is_scale=True,
                splitarea_opts=opts.SplitAreaOpts(
                    is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=1)
                ),
            ),
            datazoom_opts=[opts.DataZoomOpts(type_="inside")],
            title_opts=opts.TitleOpts(title="Kline-DataZoom-inside"),
        )
        # .render("kline_datazoom_inside.html")
    )
    return c

@app.route("/")
def index():
    c = Kline_zoom()
    return Markup(c.render_embed())
    # return c.dump_options_with_quotes()


if __name__ == "__main__":
    app.run()