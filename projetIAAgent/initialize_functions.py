from app.modules.flask login.route import flask login_bp
from app.modules.flask.route import flask_bp
from flask import Flask
from flasgger import Swagger
from app.modules.Flask.route import Flask_bp
from app.db.db import db


def initialize_route(app: Flask):
    with app.app_context():
        app.register_blueprint(flask login_bp, url_prefix='/api/v1/flask login')
        app.register_blueprint(flask_bp, url_prefix='/api/v1/flask')
        app.register_blueprint(Flask_bp, url_prefix='/api/v1/Flask')


def initialize_db(app: Flask):
    with app.app_context():
        db.init_app(app)
        db.create_all()

def initialize_swagger(app: Flask):
    with app.app_context():
        swagger = Swagger(app)
        return swagger