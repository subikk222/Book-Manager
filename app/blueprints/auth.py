from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(username) < 8 or len(username) > 50 or not password:
            flash("Username must be 8-50 characters and password is required.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        else:
            try:
                user = User(
                    username=username,
                    password=generate_password_hash(password),
                )
                db.session.add(user)
                db.session.commit()
                flash("Account created successfully.", "success")
                return redirect(url_for("auth.login"))
            except IntegrityError:
                db.session.rollback()
                flash("Username already exists.", "error")

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Login successful.", "success")
            return redirect(url_for("books.index"))

        flash("Login failed.", "error")

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Logout successful.", "success")
    return redirect(url_for("books.index"))
