import os
from flask import Flask, send_from_directory
from app.database import initialize_mysql_database
from app.routes.auth import AuthRoutes

def create_app():
    app = Flask(__name__, 
                static_url_path='/static',
                static_folder='static', # Flask will look in app/static/
                template_folder='templates') # Flask will look in app/templates/
                
    app.config.from_object("config")
    app.secret_key = app.config["SECRET_KEY"]
    initialize_mysql_database()
    
    @app.route('/image/<filename>')
    def serve_image(filename):
        return send_from_directory(os.path.join(os.path.dirname(__file__), 'image'), filename)

    auth_routes = AuthRoutes()
    app.register_blueprint(auth_routes.register_routes())

    return app