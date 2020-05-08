from random import randrange
from flask import Flask, render_template
from jinja2 import Markup
from pyecharts import options as opts
from pyecharts.charts import Bar


import Kpro

app = Flask(__name__, 
                        static_url_path='/',
                        static_folder='static',
                        template_folder='templates')


# def bar_base() -> Bar:
#     c = (
#         Bar()
#         .add_xaxis(["衬衫", "羊毛衫", "雪纺衫", "裤子", "高跟鞋", "袜子"])
#         .add_yaxis("商家A", [randrange(0, 100) for _ in range(6)])
#         .add_yaxis("商家B", [randrange(0, 100) for _ in range(6)])
#         .set_global_opts(title_opts=opts.TitleOpts(title="Bar-基本示例", subtitle="我是副标题"))
#     )
#     return c


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/gridChart")
def get_grid_chart():
    c = Kpro.Kchart('002110')
    return c.dump_options_with_quotes()
    


if __name__ == "__main__":
    app.run()