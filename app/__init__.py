import os

from flask import Flask

from config import Config
from app.extensions import db


def create_app(config_class=Config):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.config.from_object(config_class)

    db.init_app(app)

    from app.blueprints import auth, books, cart, chat

    app.register_blueprint(auth.bp)
    app.register_blueprint(books.bp)
    app.register_blueprint(cart.bp)
    app.register_blueprint(chat.bp)

    with app.app_context():
        from app import models  # noqa: F401

        db.create_all()

    return app
