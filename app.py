from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "library_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lib.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
DATABASE = "lib.db"
db = SQLAlchemy(app)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            year INTEGER NOT NULL,
            genre TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS book_quantities (
            book_id INTEGER PRIMARY KEY,
            quantity INTEGER NOT NULL DEFAULT 10 CHECK(quantity >= 0),
            FOREIGN KEY (book_id) REFERENCES books(id)
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity >= 0),
            UNIQUE(user_id, book_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (book_id) REFERENCES books(id)
        );

        CREATE TABLE IF NOT EXISTS borrowings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity >= 0),
            returned_quantity INTEGER NOT NULL DEFAULT 0,
            borrowed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (book_id) REFERENCES books(id)
        );

        INSERT OR IGNORE INTO book_quantities (book_id, quantity)
        SELECT id, 10 FROM books;
        
        CREATE TABLE IF NOT EXISTS review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (book_id) REFERENCES books(id),
            UNIQUE(user_id, book_id)
        );
        
        CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,

        is_updated BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (is_updated IN (0, 1)),

        created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id)
);
    """)

    conn.commit()
    conn.close()


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(50), nullable=False)
    text = db.Column(db.String(500), nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


def login_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("You need to login first.", "error")
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    conn = get_db_connection()
    search = request.args.get("search", "")
    fields = request.args.getlist("field")
    sort = request.args.get("sort")

    query = """
        SELECT books.*, COALESCE(book_quantities.quantity, 10) AS stock
        FROM books
        LEFT JOIN book_quantities ON books.id = book_quantities.book_id
    """
    params = []

    allowed = ["title", "author", "genre", "year"]
    conditions = []

    if search:
        for field in fields or ["title"]:
            if field in allowed:
                conditions.append(f"CAST(books.{field} AS TEXT) LIKE ?")
                params.append(f"%{search}%")

        if conditions:
            query += " WHERE " + " OR ".join(conditions)

    if sort in ("asc", "desc"):
        query += f" ORDER BY books.year {sort.upper()}"

    books = conn.execute(query, params).fetchall()

    popular_books = conn.execute("""
        SELECT 
            books.id,
            books.title,
            books.image,
            ROUND(AVG(review.rating), 1) AS average_rating,
            COUNT(review.id) AS review_count
        FROM books
        JOIN review ON books.id = review.book_id
        GROUP BY books.id
        ORDER BY AVG(review.rating) DESC, COUNT(review.id) DESC
        LIMIT 5;
    """).fetchall()

    conn.close()

    return render_template(
        "index.html", books=books, count=len(books), search=search, popular_books=popular_books
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        data = tuple(request.form.get(key, "") for key in
                     ("image", "title", "author", "year", "genre"))

        conn = get_db_connection()
        cursor = conn.execute("""
            INSERT INTO books (image, title, author, year, genre)
            VALUES (?, ?, ?, ?, ?)
        """, data)

        conn.execute(
            "INSERT INTO book_quantities (book_id, quantity) VALUES (?, 10)",
            (cursor.lastrowid,)
        )
        conn.commit()
        conn.close()

        flash("New book was successfully added.", "success")
        return redirect(url_for("index"))

    return render_template("add.html")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (id,)).fetchone()

    if book is None:
        conn.close()
        flash("Book not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        data = tuple(request.form.get(key, "") for key in
                     ("image", "title", "author", "year", "genre"))

        conn.execute("""
            UPDATE books SET image=?, title=?, author=?, year=?, genre=?
            WHERE id=?
        """, (*data, id))
        conn.commit()
        conn.close()

        flash("Book was successfully updated.", "success")
        return redirect(url_for("index"))

    conn.close()
    return render_template("edit.html", book=book)


@app.route("/delete/<int:id>", methods=["GET", "POST"])
@login_required
def delete(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM cart WHERE book_id = ?", (id,))
    conn.execute("DELETE FROM book_quantities WHERE book_id = ?", (id,))
    conn.execute("DELETE FROM books WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("Book was successfully deleted.", "success")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
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
            conn = get_db_connection()
            try:
                conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )
                conn.commit()
                flash("Account created successfully.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username already exists.", "error")
            finally:
                conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Login successful.", "success")
            return redirect(url_for("index"))

        flash("Login failed.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logout successful.", "success")
    return redirect(url_for("index"))


@app.route("/cart")
@login_required
def view_cart():
    conn = get_db_connection()
    items = conn.execute("""
        SELECT cart.id, cart.book_id, cart.quantity, books.title, books.image,
               book_quantities.quantity AS stock
        FROM cart
        JOIN books ON books.id = cart.book_id
        JOIN book_quantities ON books.id = book_quantities.book_id
        WHERE cart.user_id = ?
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("cart.html", items=items)


@app.route("/cart/remove/<int:cart_id>", methods=["POST"])
@login_required
def remove_from_cart(cart_id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM cart WHERE id=? AND user_id=?",
        (cart_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    flash("Book removed from cart.", "success")
    return redirect(url_for("view_cart"))


@app.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required
def add_to_cart(book_id):
    try:
        quantity = int(request.form.get("quantity", 1))
        if quantity < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash("Invalid quantity.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")
        book = conn.execute(
            "SELECT quantity FROM book_quantities WHERE book_id=?",
            (book_id,)
        ).fetchone()

        if not book:
            flash("Book not found.", "error")
        else:
            existing = conn.execute(
                "SELECT quantity FROM cart WHERE user_id=? AND book_id=?",
                (session["user_id"], book_id)
            ).fetchone()

            current = existing["quantity"] if existing else 0

            if current + quantity > book["quantity"]:
                flash(f"Not enough stock. Available: {book['quantity']}.", "error")
            else:
                conn.execute("""
                    INSERT INTO cart (user_id, book_id, quantity)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, book_id)
                    DO UPDATE SET quantity = quantity + excluded.quantity
                """, (session["user_id"], book_id, quantity))
                flash("Book added to cart successfully.", "success")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return redirect(url_for("index"))


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    conn = get_db_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")
        user_id = session["user_id"]

        items = conn.execute("""
            SELECT cart.book_id, cart.quantity, book_quantities.quantity AS stock
            FROM cart
            JOIN book_quantities ON cart.book_id = book_quantities.book_id
            WHERE cart.user_id = ?
        """, (user_id,)).fetchall()

        if not items:
            conn.rollback()
            flash("Your cart is empty.", "error")
            return redirect(url_for("view_cart"))

        if any(item["quantity"] > item["stock"] for item in items):
            conn.rollback()
            flash("Not enough books in stock.", "error")
            return redirect(url_for("view_cart"))

        for item in items:
            conn.execute("""
                INSERT INTO borrowings (user_id, book_id, quantity)
                VALUES (?, ?, ?)
            """, (user_id, item["book_id"], item["quantity"]))

            conn.execute("""
                UPDATE book_quantities SET quantity = quantity - ?
                WHERE book_id = ?
            """, (item["quantity"], item["book_id"]))

        conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        conn.commit()
        flash("Books borrowed successfully!", "success")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return redirect(url_for("my_borrowings"))


@app.route("/my_borrowings")
@login_required
def my_borrowings():
    conn = get_db_connection()
    borrowings = conn.execute("""
        SELECT borrowings.id, books.title, borrowings.quantity,
               borrowings.returned_quantity, borrowings.borrowed_at
        FROM borrowings
        JOIN books ON books.id = borrowings.book_id
        WHERE borrowings.user_id = ?
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("my_borrowings.html", borrowings=borrowings)

@app.route("/chat")
@login_required
def chat():
    messages = Message.query.order_by(Message.created_at.asc()).all()
    return render_template("chat.html", messages=messages)


@app.route("/chat/send", methods=["POST"])
@login_required
def send_message():
    text = request.form.get("message", "").strip()

    if text:
        message = Message(
            user_id=session["user_id"],
            username=session["username"],
            text=text[:500]
        )
        db.session.add(message)
        db.session.commit()
    return redirect(url_for("chat"))


@app.route("/chat/update/<int:message_id>", methods=["POST"])
@login_required
def update_message(message_id):
    message = Message.query.filter_by(id=message_id, user_id=session["user_id"]).first()

    new_text = request.form.get("message", "").strip()

    if message and new_text:
        message.text = new_text[:500]
        db.session.commit()

    return redirect(url_for("chat"))

@app.route("/chat/delete/<int:message_id>", methods=["POST"])
@login_required
def delete_message(message_id):
    message = Message.query.filter_by(id=message_id, user_id=session["user_id"]).first()

    if message:
        db.session.delete(message)
        db.session.commit()

    return redirect(url_for("chat"))

@app.route("/review/<int:book_id>", methods=["GET", "POST"])
@login_required
def review(book_id):
    conn = get_db_connection()
    book = conn.execute(
        "SELECT * FROM books WHERE id = ?", (book_id,)
    ).fetchone()
    if book is None:
        conn.close()
        flash("Book not found.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment", "").strip()

        if rating is None or rating < 1 or rating > 5 or not comment:
            flash("Invalid rating.", "error")
        else:
            try:
                conn.execute("""
                    INSERT INTO review (user_id, book_id, rating, comment)
                    VALUES (?, ?, ?, ?)
                """, (session["user_id"], book_id, rating, comment))
                conn.commit()
                flash("Review submitted.", "success")
                conn.close()
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("You already reviewed this book.", "error")

    reviews = conn.execute("""
        SELECT review.rating, review.comment, users.username
        FROM review
        JOIN users ON review.user_id = users.id
        WHERE review.book_id = ?
        ORDER BY review.id DESC
    """, (book_id,)).fetchall()

    conn.close()
    return render_template("review.html", book=book, reviews=reviews)

with app.app_context():
    db.create_all()
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
