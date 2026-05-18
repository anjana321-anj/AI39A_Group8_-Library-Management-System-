from flask import Flask
from app.routes.auth import AuthRoutes
import os

def create_app():
    # Configure Flask to serve both static and image folders
    app = Flask(__name__, 
                static_url_path='/static',
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Add image folder as an additional static folder
    @app.route('/image/<filename>')
    def serve_image(filename):
        from flask import send_from_directory
        return send_from_directory(os.path.join(os.path.dirname(__file__), 'image'), filename)

    auth_routes = AuthRoutes()
    app.register_blueprint(auth_routes.register_routes())

    return app
