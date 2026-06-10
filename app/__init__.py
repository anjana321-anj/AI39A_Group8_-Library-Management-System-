import os

from flask import Flask

from app.database import initialize_mysql_database
from app.routes.auth import AuthRoutes

def create_app():
    # Configure Flask to serve both static and image folders
    app = Flask(__name__,
                static_url_path='/static',
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    app.config.from_object("config")
    app.secret_key = app.config["SECRET_KEY"]
    initialize_mysql_database()
    
    # Add image folder as an additional static folder
    @app.route('/image/<filename>')
    def serve_image(filename):
        from flask import send_from_directory
        return send_from_directory(os.path.join(os.path.dirname(__file__), 'image'), filename)

    auth_routes = AuthRoutes()
    app.register_blueprint(auth_routes.register_routes())

    return app
