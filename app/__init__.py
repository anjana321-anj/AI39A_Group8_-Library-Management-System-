import os
<<<<<<< HEAD
from flask import Flask, send_from_directory
=======

from flask import Flask

>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
from app.database import initialize_mysql_database
from app.routes.auth import AuthRoutes

def create_app():
<<<<<<< HEAD
    app = Flask(__name__, 
                static_url_path='/static',
                static_folder='static', # Flask will look in app/static/
                template_folder='templates') # Flask will look in app/templates/
                
=======
    # Configure Flask to serve both static and image folders
    app = Flask(__name__,
                static_url_path='/static',
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
    app.config.from_object("config")
    app.secret_key = app.config["SECRET_KEY"]
    initialize_mysql_database()
    
<<<<<<< HEAD
    @app.route('/image/<filename>')
    def serve_image(filename):
=======
    # Add image folder as an additional static folder
    @app.route('/image/<filename>')
    def serve_image(filename):
        from flask import send_from_directory
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
        return send_from_directory(os.path.join(os.path.dirname(__file__), 'image'), filename)

    auth_routes = AuthRoutes()
    app.register_blueprint(auth_routes.register_routes())

<<<<<<< HEAD
    return app
=======
    return app
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
