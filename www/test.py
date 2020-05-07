from flask import Flask, escape, request, redirect
from jinja2 import Markup, Environment, FileSystemLoader
from pyecharts.globals import CurrentConfig

from pyecharts import options as opts
from pyecharts.charts import Bar, Grid, Line, Pie, Tab
from pyecharts.faker import Faker
import mytab
import mytable
import Kpro
app = Flask(__name__, 
                        static_url_path='/',
                        static_folder='static',
                        template_folder='templates')

@app.route("/")
def index():
    c = mytab.tab()
    b = mytable.table()
    e = Kpro.Kchart('002194')
    return e.render_embed()
    

if __name__ == "__main__":
    app.run()