from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import cast, func, or_, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.decorators import login_required
from app.extensions import db
from app.models import Book, BookQuantity, CartItem, Review

bp = Blueprint("books", __name__)


@bp.route("/")
def index():
    search = request.args.get("search", "")
    fields = request.args.getlist("field")
    sort = request.args.get("sort")

    query = Book.query.outerjoin(BookQuantity)

    allowed = {"title": Book.title, "author": Book.author, "genre": Book.genre, "year": Book.year}
    if search:
        selected = fields or ["title"]
        conditions = []
        for field in selected:
            column = allowed.get(field)
            if column is not None:
                conditions.append(cast(column, String).like(f"%{search}%"))
        if conditions:
            query = query.filter(or_(*conditions))

    if sort in ("asc", "desc"):
        query = query.order_by(Book.year.asc() if sort == "asc" else Book.year.desc())

    books = query.all()

    popular_books = (
        db.session.query(
            Book.id,
            Book.title,
            Book.image,
            func.round(func.avg(Review.rating), 1).label("average_rating"),
            func.count(Review.id).label("review_count"),
        )
        .join(Review, Review.book_id == Book.id)
        .group_by(Book.id)
        .order_by(func.avg(Review.rating).desc(), func.count(Review.id).desc())
        .limit(5)
        .all()
    )

    return render_template(
        "index.html",
        books=books,
        count=len(books),
        search=search,
        popular_books=popular_books,
    )


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        try:
            year = int(request.form.get("year", ""))
        except (TypeError, ValueError):
            flash("Year must be a number.", "error")
            return render_template("add.html")

        book = Book(
            image=request.form.get("image", ""),
            title=request.form.get("title", ""),
            author=request.form.get("author", ""),
            year=year,
            genre=request.form.get("genre", ""),
        )
        db.session.add(book)
        db.session.flush()
        db.session.add(BookQuantity(book_id=book.id, quantity=10))
        db.session.commit()

        flash("New book was successfully added.", "success")
        return redirect(url_for("books.index"))

    return render_template("add.html")


@bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    book = Book.query.get(id)
    if book is None:
        flash("Book not found.", "error")
        return redirect(url_for("books.index"))

    if request.method == "POST":
        try:
            year = int(request.form.get("year", ""))
        except (TypeError, ValueError):
            flash("Year must be a number.", "error")
            return render_template("edit.html", book=book)

        book.image = request.form.get("image", "")
        book.title = request.form.get("title", "")
        book.author = request.form.get("author", "")
        book.year = year
        book.genre = request.form.get("genre", "")
        db.session.commit()

        flash("Book was successfully updated.", "success")
        return redirect(url_for("books.index"))

    return render_template("edit.html", book=book)


@bp.route("/delete/<int:id>", methods=["GET", "POST"])
@login_required
def delete(id):
    book = Book.query.get(id)
    if book is None:
        flash("Book not found.", "error")
        return redirect(url_for("books.index"))

    CartItem.query.filter_by(book_id=id).delete()
    Review.query.filter_by(book_id=id).delete()
    BookQuantity.query.filter_by(book_id=id).delete()
    db.session.delete(book)
    db.session.commit()

    flash("Book was successfully deleted.", "success")
    return redirect(url_for("books.index"))


@bp.route("/review/<int:book_id>", methods=["GET", "POST"])
@login_required
def review(book_id):
    book = Book.query.get(book_id)
    if book is None:
        flash("Book not found.", "error")
        return redirect(url_for("books.index"))

    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment", "").strip()

        if rating is None or rating < 1 or rating > 5 or not comment:
            flash("Invalid rating.", "error")
        else:
            try:
                db.session.add(
                    Review(
                        user_id=session["user_id"],
                        book_id=book_id,
                        rating=rating,
                        comment=comment,
                    )
                )
                db.session.commit()
                flash("Review submitted.", "success")
                return redirect(url_for("books.index"))
            except IntegrityError:
                db.session.rollback()
                flash("You already reviewed this book.", "error")

    reviews = (
        Review.query.options(joinedload(Review.user))
        .filter_by(book_id=book_id)
        .order_by(Review.id.desc())
        .all()
    )
    return render_template("review.html", book=book, reviews=reviews)
