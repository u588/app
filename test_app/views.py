from datetime import datetime

from flask import Flask, render_template

# from . import app

app = Flask(__name__, 
                    template_folder='/home/ts/app/test_app/templates',
                    static_folder='/home/ts/app/test_app/static'     )

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
    return render_template(
        "hello_there.html",
        name=name,
        date=datetime.now()
    )

@app.route("/api/data")
def get_data():
    return app.send_static_file("data.json")

# if __name__ == '__main__':
#     app.run()