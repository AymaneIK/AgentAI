import unittest
import json

from app.modules.flask.controller import FlaskController


def test_index():
    flask_controller = FlaskController()
    result = flask_controller.index()
    assert result == {'message': 'Hello, World!'}
