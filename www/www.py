from datetime import datetime
from flask import Flask, render_template
from jinja2 import Markup, Environment, FileSystemLoader

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

@app.route("/gridChart")
def gridChart():
    c = Kpro.Kchart('600015')
    return c.dump_options_with_quotes()

@app.route("/tabChart")
def tabChart():
    c = mytab.tab()
    return c.render_embed()

@app.route("/test/<codeID>")
def test(codeID):
    c = Kpro.Kchart(codeID)
    return c.render_embed()

@app.route("/api/data")
def get_data():
    return app.send_static_file("data.json")

if __name__ == '__main__':
    app.run()