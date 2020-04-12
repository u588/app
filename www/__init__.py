import flask
app = flask.Flask(__name__, 
                    template_folder='/home/ts/app/www/templates',
                    static_folder='/home/ts/app/www/static'     )