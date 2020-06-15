from datetime import datetime
from flask import Flask, render_template, redirect, request
from jinja2 import Markup, Environment, FileSystemLoader

import mytab
import mytable
import Kpro
import geoGrid
import timel
import griRada


app = Flask(__name__, 
                    static_url_path='/',
                    template_folder='templates',
                    static_folder='static')

@app.route("/")
def root():
    return redirect("/login")

@app.route('/login/',methods=['GET','POST']) 
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'root' and password == 'system6^':
            return render_template('home.html')
        return render_template('login.html', msg='密码错误!!! ')

@app.route("/home/")
def home():
    return render_template("home.html")

@app.route("/about/")
def about():
    return render_template("about.html")

@app.route("/contact/")
def contact():
    return render_template("contact.html")

@app.route("/gridChart/<codeID>")
def gridChart(codeID):
    c = Kpro.Kchart(codeID)
    # return c.dump_options_with_quotes()
    return c.render_embed()

@app.route("/gridRada/<Date>")
def gridRada(Date):
    c = griRada.grid(Date)
    return c.render_embed()

@app.route('/test')
def test1():
    c = geoGrid.colBar()
    return c.dump_options_with_quotes()

@app.route("/tabChart")
def tabChart():
    c = mytab.tab()
    return c.render_embed()

@app.route("/tableChart")
def tableChart():
    c = mytable.table()
    return c.render_embed()

@app.route("/datetime")
def datetim():
    c = getData.getDate()
    return c

@app.route("/getStock/<dateID>")
def getStock(dateID):
    c = getData.getCode(dateID)
    return c

@app.route("/tl/<dateID>")
def tlChart(dateID):
    c = timel.pie(dateID)
    return c.dump_options_with_quotes()

@app.route("/test/<codeID>")
def test(codeID):
    c = Kpro.Kchart(codeID)
    return c.render_embed()

@app.route("/api/data")
def get_data():
    return app.send_static_file("data.json")

if __name__ == '__main__':
    app.run()