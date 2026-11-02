import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "lib.db")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "library_secret_key")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + DATABASE_PATH.replace("\\", "/")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
