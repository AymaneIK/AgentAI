import unittest
import json

from app.modules.flask login.controller import Flask loginController


def test_index():
    flask login_controller = Flask loginController()
    result = flask login_controller.index()
    assert result == {'message': 'Hello, World!'}
