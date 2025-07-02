from flask import Flask, render_template, request, redirect, flash, session
from functools import wraps
from datetime import datetime
import sqlite3
import os
import hashlib
#--------------------------------------------------------------------------------------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
#--------------------------------------------------------------------------------------------------------------------------------------------------------

def get_db_connection():
    conn = sqlite3.connect("lms_basic.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
#--------------------------------------------------------------------------------------------------------------------------------------------------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
#--------------------------------------------------------------------------------------------------------------------------------------------------------

def get_user_id_from_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result['id'] if result else None
#--------------------------------------------------------------------------------------------------------------------------------------------------------

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'role' not in session:
                return "You must log in to access this page.", 401
            if session['role'] not in allowed_roles:
                return "Access Denied: You do not have permission.", 403
            return f(*args, **kwargs)
        return wrapped
    return decorator
#--------------------------------------------------------------------------------------------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('lms.html')
#--------------------------------------------------------------------------------------------------------------------------------------------------------

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    hashed_password = hash_password(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE username=? AND password=?",
                          (username, hashed_password)).fetchone()
    conn.close()

    if user:
        session['username'] = user['username']
        session['role'] = user['role']
        return redirect('/')
    else:
        flash("Invalid credentials")
        return redirect('/')
#--------------------------------------------------------------------------------------------------------------------------------------------------------

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
#--------------------------------------------------------------------------------------------------------------------------------------------------------

def add_a_user(username, password, first_name, last_name, contact_number, contact_email, residency, age, creation_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed_password = hash_password(password)

    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return "Username already exists."

        cursor.execute("""
            INSERT INTO users 
            (username, password, first_name, last_name, contact_number, contact_email, residency, age, number_of_issued_books, role, creation_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'user', ?) 
        """, (username, hashed_password, first_name, last_name, contact_number, contact_email, residency, age, creation_date))
        conn.commit()
        return f"User {first_name} added successfully."
    except sqlite3.Error:
        return "Database error."
    finally:
        conn.close()

@app.route('/add-user', methods=['GET', 'POST'])
@role_required('admin', 'librarian')
def add_user_route():
    if request.method == 'POST':
        data = request.form
        result = add_a_user(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            contact_number=data['contact_number'],
            contact_email=data['contact_email'],
            residency=data['residency'],
            age=data['age'],
            creation_date=datetime.now().strftime('%Y-%m-%d')
        )
        flash(result)
        return redirect('/books')
    return redirect('/')


#--------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route('/books')
def see_all_books():
    conn = get_db_connection()
    books = conn.execute("SELECT * FROM books").fetchall()
    conn.close()
    return render_template('lms.html', books=books)

#--------------------------------------------------------------------------------------------------------------------------------------------------------
# Search by title
def book_by_title(title):
    conn = get_db_connection()
    cursor = conn.cursor()
    keywords = title.strip().split()
    query = "SELECT * FROM books WHERE " + " AND ".join(["LOWER(title) LIKE ?"] * len(keywords))
    values = ['%' + word.lower() + '%' for word in keywords]
    try: 
        cursor.execute(query, values)
        result = cursor.fetchall()
        return result

    except sqlite3.Error:
        flash("Database error")

    finally: 
        conn.close()

@app.route('/search-title', methods=['GET', 'POST'])
def search_books_title():
    results = []
    if request.method == 'POST':
        title = request.form['title']
        results = book_by_title(title)
    return render_template('lms.html', results=results)
#--------------------------------------------------------------------------------------------------------------------------------------------------------
# Search by author
def book_by_author(author):
    conn = get_db_connection()
    cursor = conn.cursor()
    keywords = author.strip().split()
    query = "SELECT * FROM books WHERE " + " AND ".join(["LOWER(author) LIKE ?"] * len(keywords))
    values = ['%' + word.lower() + '%' for word in keywords]
    try:
        cursor.execute(query, values)
        result = cursor.fetchall()
        return result
    except sqlite3.Error:
        flash("Database error")
    finally:
        conn.close()
    
@app.route('/search-author', methods=['GET', 'POST'])
def search_books_author():
    results = []
    if request.method == 'POST':
        author = request.form['author']
        results = book_by_author(author)
    return render_template('lms.html', results=results)
#--------------------------------------------------------------------------------------------------------------------------------------------------------

# Search by ISBN
def book_by_ISBN(ISBN):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM books WHERE ISBN = ?", (ISBN,))
        result = cursor.fetchall()
        return result
    except sqlite3.Error:
        flash("Database Error")
    finally:
        conn.close()

@app.route('/search-isbn', methods=['GET', 'POST'])
def search_by_isbn():
    results = []
    if request.method == 'POST':
        isbn = request.form['isbn']
        results = book_by_ISBN(isbn)
    return render_template('lms.html', results=results)
#--------------------------------------------------------------------------------------------------------------------------------------------------------

# Search by availability
def book_by_availability():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM books WHERE LOWER(status) = 'available'")
        result = cursor.fetchall()
        return result
    except sqlite3.Error:
        flash("Database Error")
    finally:
        conn.close()

@app.route('/available')
def show_available_books():
    results = book_by_availability()
    return render_template('lms.html', results=results)
#--------------------------------------------------------------------------------------------------------------------------------------------------------

# Book by ID 
def book_by_id(book_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try: 
        cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        result = cursor.fetchall()
        return result
    except sqlite3.Error:
        flash("Database Error")
    finally:
        conn.close()

@app.route('/bookid', methods=['POST'])
def show_book_by_id():
    book_id = request.form['book_id']
    results = book_by_id(book_id)
    return render_template('lms.html', results=results)
#--------------------------------------------------------------------------------------------------------------------------------------------------------
def add_a_book(ISBN, title, author, publisher, genre, price, min_age, pages):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO books (ISBN, title, author,publisher, genre, price, min_age, pages, status)
            VALUES (?, ?, ?, ?, ?, ?, ? , ?, 'available')
        """, (ISBN, title, author, publisher, genre, price, min_age, pages))
        conn.commit()
        return f"Added book: {title}"
    except sqlite3.Error:
        flash("Database Error")
    finally:
        conn.close()

@app.route('/add-book', methods=['GET', 'POST'])
@role_required('admin', 'librarian')

def add_book_route():
    message = ''
    if request.method == 'POST':
        ISBN = request.form['ISBN']
        title = request.form['title']
        author = request.form['author']
        publisher = request.form['publisher']
        genre = request.form['genre']
        price = request.form['price']
        min_age = request.form['min_age']
        pages = request.form['pages']
        message = add_a_book(ISBN, title, author, publisher, genre, price, min_age, pages)
    return render_template('lms.html', message=message)

#--------------------------------------------------------------------------------------------------------------------------------------------------------

def issue_a_book(book_id, title, user_id, issue_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT status FROM books WHERE id = ?", (book_id,))
        book_status = cursor.fetchone()
        if not book_status:
            return "Book not found."
        if book_status['status'].lower() != "available":
            return "Book is not available."

        cursor.execute("SELECT number_of_issued_books FROM users WHERE id = ?", (user_id,))
        issued_books = cursor.fetchone()
        if not issued_books:
            return "User not found."
        if issued_books['number_of_issued_books'] >= 4:
            return "User has reached maximum issue limit."

        cursor.execute("UPDATE books SET status = 'issued' WHERE id = ?", (book_id,))
        cursor.execute("INSERT INTO book_user (book_id, issue_date, user_id) VALUES (?, ?, ?)",
                       (book_id, issue_date, user_id))
        cursor.execute("UPDATE users SET number_of_issued_books = number_of_issued_books + 1 WHERE id = ?",
                       (user_id,))
        conn.commit()
        return f"Book '{title}' issued to user {user_id}."
    except sqlite3.Error:
        return "Database error."
    finally:
        conn.close()

@app.route('/issue-book', methods=['POST'])
@role_required('admin', 'librarian', 'user')
def issue_book_route():
    book_id = request.form['book_id']
    title = request.form['title']
    issue_date = request.form['issue_date']
    user_id = get_user_id_from_username(session['username'])
    message = issue_a_book(book_id, title, user_id, issue_date)
    flash(message)
    return redirect('/books')

#--------------------------------------------------------------------------------------------------------------------------------------------------------
def return_a_book(book_id, title, user_id, return_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT status FROM books WHERE id = ?", (book_id,))
        result = cursor.fetchone()
        if not result or result['status'].lower() != "issued":
            return "Book is not currently issued."

        cursor.execute("UPDATE books SET status = 'available' WHERE id = ?", (book_id,))
        cursor.execute("INSERT INTO book_user (book_id, return_date, user_id) VALUES (?, ?, ?)",
                       (book_id, return_date, user_id))
        cursor.execute("UPDATE users SET number_of_issued_books = number_of_issued_books - 1 WHERE id = ?",
                       (user_id,))
        conn.commit()
        return f"Book '{title}' returned by user {user_id}."
    except sqlite3.Error:
        return "Database error."
    finally:
        conn.close()

@app.route('/return-book', methods=['POST'])
@role_required('admin', 'librarian')
def return_book_route():
    book_id = request.form['book_id']
    title = request.form['title']
    return_date = request.form['return_date']
    user_id = get_user_id_from_username(session['username'])
    message = return_a_book(book_id, title, user_id, return_date)
    flash(message)
    return redirect('/books')

#--------------------------------------------------------------------------------------------------------------------------------------------------------
def delete_book(book_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if book exists
        cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        book = cursor.fetchone()
        if not book:
            return f"No book found with ID {book_id}."

        # Delete the book
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
        return f"Book with ID {book_id} deleted successfully."

    except sqlite3.Error:
        return "Database error occurred while deleting book."
    finally:
        conn.close()

@app.route('/delete-book', methods=['POST'])
@role_required('admin', 'librarian')
def delete_book_route():
    book_id = request.form['book_id']
    message = delete_book(book_id)
    flash(message)
    return redirect('/books')
    
#--------------------------------------------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5000)
