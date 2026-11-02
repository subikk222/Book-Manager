from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.decorators import login_required
from app.extensions import db
from app.models import Book, BookQuantity, Borrowing, CartItem

bp = Blueprint("cart", __name__)


@bp.route("/cart")
@login_required
def view_cart():
    items = (
        db.session.query(
            CartItem.id,
            CartItem.book_id,
            CartItem.quantity,
            Book.title,
            Book.image,
            BookQuantity.quantity.label("stock"),
        )
        .join(Book, Book.id == CartItem.book_id)
        .join(BookQuantity, BookQuantity.book_id == Book.id)
        .filter(CartItem.user_id == session["user_id"])
        .all()
    )
    return render_template("cart.html", items=items)


@bp.route("/cart/remove/<int:cart_id>", methods=["POST"])
@login_required
def remove_from_cart(cart_id):
    item = CartItem.query.filter_by(id=cart_id, user_id=session["user_id"]).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Book removed from cart.", "success")
    return redirect(url_for("cart.view_cart"))


@bp.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required
def add_to_cart(book_id):
    try:
        quantity = int(request.form.get("quantity", 1))
        if quantity < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash("Invalid quantity.", "error")
        return redirect(url_for("books.index"))

    stock_row = BookQuantity.query.filter_by(book_id=book_id).first()
    if not stock_row:
        flash("Book not found.", "error")
        return redirect(url_for("books.index"))

    existing = CartItem.query.filter_by(
        user_id=session["user_id"], book_id=book_id
    ).first()
    current = existing.quantity if existing else 0

    if current + quantity > stock_row.quantity:
        flash(f"Not enough stock. Available: {stock_row.quantity}.", "error")
    else:
        if existing:
            existing.quantity = current + quantity
        else:
            db.session.add(
                CartItem(
                    user_id=session["user_id"],
                    book_id=book_id,
                    quantity=quantity,
                )
            )
        db.session.commit()
        flash("Book added to cart successfully.", "success")

    return redirect(url_for("books.index"))


@bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    user_id = session["user_id"]
    items = (
        db.session.query(CartItem, BookQuantity)
        .join(BookQuantity, BookQuantity.book_id == CartItem.book_id)
        .filter(CartItem.user_id == user_id)
        .all()
    )

    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart.view_cart"))

    if any(cart_item.quantity > stock.quantity for cart_item, stock in items):
        flash("Not enough books in stock.", "error")
        return redirect(url_for("cart.view_cart"))

    try:
        for cart_item, stock in items:
            db.session.add(
                Borrowing(
                    user_id=user_id,
                    book_id=cart_item.book_id,
                    quantity=cart_item.quantity,
                )
            )
            stock.quantity -= cart_item.quantity
            db.session.delete(cart_item)
        db.session.commit()
        flash("Books borrowed successfully!", "success")
    except Exception:
        db.session.rollback()
        raise

    return redirect(url_for("cart.my_borrowings"))


@bp.route("/my_borrowings")
@login_required
def my_borrowings():
    borrowings = (
        Borrowing.query.filter_by(user_id=session["user_id"])
        .order_by(Borrowing.id.desc())
        .all()
    )
    return render_template("my_borrowings.html", borrowings=borrowings)
