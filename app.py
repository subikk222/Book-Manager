from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3

app = Flask(__name__)
app.secret_key = 'library_secret_key'

DATABASE = "lib.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image TEXT NOT NULL,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        year INTEGER NOT NULL,
        genre TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

@app.route('/')
def index():
    search = request.args.get("search", "")
    sort = request.args.get("sort", "")

    conn = get_db_connection()

    if search:
        fields = request.args.getlist("field")

        allowed_fields = ["title", "author", "genre", "year"]

        fields = [field for field in fields if field in allowed_fields]

        if not fields:
            fields = ["title"]

        conditions = " OR ".join(
            [f"{field} LIKE ?" for field in fields]
        )

        search_value = f"%{search}%"

        books = conn.execute(
            f"SELECT * FROM books WHERE {conditions}",
            tuple(search_value for _ in fields)
        ).fetchall()
    elif sort == "asc":
        books = conn.execute(
            "SELECT * FROM books ORDER BY year ASC"
        ).fetchall()
    elif sort == "desc":
        books = conn.execute(
            "SELECT * FROM books ORDER BY year DESC"
        ).fetchall()
    else:
        books = conn.execute(
            "SELECT * FROM books"
        ).fetchall()

    count = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    conn.close()

    return render_template("index.html", books=books, count=count, search=search, sort=sort)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == "POST":
        image = request.form["image"]
        title = request.form.get("title")
        author = request.form.get("author")
        year = request.form.get("year")
        genre = request.form.get("genre")

        conn = get_db_connection()

        conn.execute(
            """INSERT INTO books (image, title, author, year, genre)
            VALUES (?, ?, ?, ?, ?)""", (image, title, author, year, genre)
        )
        conn.commit()
        conn.close()

        flash("New book was successfully added", "success")
        return redirect(url_for("index"))

    return render_template("add.html")

@app.route('/edit/<id>', methods=['GET', 'POST'])
def edit(id):
    conn = get_db_connection()
    book = conn.execute(
        "SELECT * FROM books WHERE id = ?", (id,)
    ).fetchone()

    if book is None:
        conn.close()
        flash("Book not found", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        image = request.form["image"]
        title = request.form.get("title")
        author = request.form.get("author")
        year = request.form.get("year")
        genre = request.form.get("genre")

        conn.execute("""
            UPDATE books
            SET image = ?, title = ?, author = ?, year = ?, genre = ?
            WHERE id = ?
            """, (image, title, author, year, genre, id)
        )
        conn.commit()
        conn.close()
        flash("Book was successfully updated", "success")
        return redirect(url_for("index"))

    conn.close()
    return render_template("edit.html", book=book)

@app.route('/delete/<id>', methods=['GET', 'POST'])
def delete(id):
    conn = get_db_connection()
    conn.execute(
        """DELETE FROM books WHERE id = ?""", (id,)
    )

    conn.commit()
    conn.close()

    flash("Book was successfully deleted", "success")
    return redirect(url_for("index"))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
