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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/gridChart")
def get_grid_chart():
    c = Kpro.Kchart('603535')
    return c.dump_options_with_quotes()
    


if __name__ == "__main__":
    app.run(debug=True)