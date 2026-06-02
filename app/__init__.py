"""
BookVerse – Application Factory
=================================
Creates and configures the Flask application instance.
All blueprints are registered here so the entry-point file stays thin.
"""

import os

from flask import Flask

from app.database import initialize_mysql_database
from app.routes.auth import AuthRoutes


def create_app():
    """
    Flask application factory.

    Reads configuration from config.py, initialises the MySQL schema, registers
    all route blueprints, and returns a ready-to-run Flask application.

    Returns
    -------
    Flask
        Fully configured application instance.
    """
    app = Flask(
        __name__,
        static_url_path="/static",
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    # Load config values from config.py
    app.config.from_object("config")
    app.secret_key = app.config["SECRET_KEY"]

    # Initialise MySQL tables and seed data
    initialize_mysql_database()

    # Serve files from the app/image directory
    @app.route("/image/<filename>")
    def serve_image(filename):
        from flask import send_from_directory
        image_dir = os.path.join(os.path.dirname(__file__), "image")
        return send_from_directory(image_dir, filename)

    # Register blueprints
    auth_routes = AuthRoutes()
    app.register_blueprint(auth_routes.register_routes())

    return app
