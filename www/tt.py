from flask import Flask, escape, request, redirect

from typing import List, Sequence, Union

from pyecharts import options as opts
from pyecharts.commons.utils import JsCode
from pyecharts.charts import Kline, Line, Bar, Grid
import Kpro


app = Flask(__name__, 
                        static_url_path='/',
                        static_folder='static',
                        template_folder='templates')




@app.route("/")
def index():
    Kpro.draw_chart('11')
    return redirect('11.html')

if __name__ == "__main__":
    app.run()