from flask import Blueprint, make_response, jsonify
from .controller import Flask loginController


flask login_bp = Blueprint('flask login', __name__)
flask login_controller = Flask loginController()
@flask login_bp.route('/', methods=['GET'])
def index():
    """ Example endpoint with simple greeting.
    ---
    tags:
      - Example API
    responses:
      200:
        description: A simple greeting
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                message:
                  type: string
                  example: "Hello World!"
    """
    result=flask login_controller.index()
    return make_response(jsonify(data=result))
      