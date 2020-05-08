from datetime import datetime
from flask import Flask, render_template

import mytab
import mytable
import Kpro



app = Flask(__name__, 
                    static_url_path='/',
                    template_folder='templates',
                    static_folder='static')

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about/")
def about():
    return render_template("about.html")

@app.route("/contact/")
def contact():
    return render_template("contact.html")

@app.route("/hello/")
@app.route("/hello/<name>")
def hello_there(name = None):

    c=Kpro.Kchart(name)


    return render_template(
        "simple_chart.html",
        c
        # date=datetime.now()
    )

@app.route("/api/data")
def get_data():
    return app.send_static_file("data.json")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='5000')