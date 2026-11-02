from flask import Blueprint, redirect, render_template, request, session, url_for

from app.decorators import login_required
from app.extensions import db
from app.models import Message

bp = Blueprint("chat", __name__)


@bp.route("/chat")
@login_required
def chat():
    messages = Message.query.order_by(Message.created_at.asc()).all()
    return render_template("chat.html", messages=messages)


@bp.route("/chat/send", methods=["POST"])
@login_required
def send_message():
    text = request.form.get("message", "").strip()
    if text:
        db.session.add(
            Message(
                user_id=session["user_id"],
                username=session["username"],
                text=text[:500],
            )
        )
        db.session.commit()
    return redirect(url_for("chat.chat"))


@bp.route("/chat/update/<int:message_id>", methods=["POST"])
@login_required
def update_message(message_id):
    message = Message.query.filter_by(
        id=message_id, user_id=session["user_id"]
    ).first()
    new_text = request.form.get("message", "").strip()
    if message and new_text:
        message.text = new_text[:500]
        db.session.commit()
    return redirect(url_for("chat.chat"))


@bp.route("/chat/delete/<int:message_id>", methods=["POST"])
@login_required
def delete_message(message_id):
    message = Message.query.filter_by(
        id=message_id, user_id=session["user_id"]
    ).first()
    if message:
        db.session.delete(message)
        db.session.commit()
    return redirect(url_for("chat.chat"))
