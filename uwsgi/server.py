from flask import Flask, escape, request, redirect

app = Flask(__name__,
                    static_url_path='/',
                    static_folder='/home/ts/app',
                    template_folder='/home/ts/app/www/templates')

@app.route('/')
def index():
    return redirect('/www/html/000001上证指数.html')
    # pass
# app.add_url_rule('/','index', index)

@app.route('/Stocks/')
def Stocks():
    return redirect('/data/FindStocks/0101.txt')

if __name__ == '__main__':
    app.run()