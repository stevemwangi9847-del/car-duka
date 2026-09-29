from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import re

auth_bp = Blueprint('auth', __name__)

DATABASE = 'database.db'


def get_db():
    """Open a database connection with safe defaults."""
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_auth_db():
    """Create users table if it doesn't exist and seed a default admin."""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'buyer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()

        existing_admin = c.execute("SELECT * FROM users WHERE role = 'admin'").fetchone()
        if not existing_admin:
            c.execute('''INSERT INTO users (full_name, email, phone, password_hash, role)
                         VALUES (?, ?, ?, ?, ?)''',
                      ('Car Duka Admin',
                       'admin@carduka.com',
                       '0718870024',
                       generate_password_hash('admin123'),
                       'admin'))
            conn.commit()
            print("✅ Default admin created: admin@carduka.com / admin123")
    finally:
        conn.close()


# ---------- Decorators ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in as admin.', 'error')
            return redirect(url_for('auth.login', next=request.path))
        if session.get('role') != 'admin':
            flash('Admin access only.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper


# ---------- Routes ----------
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not full_name or not email or not password:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('auth.register'))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('auth.register'))

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('auth.register'))

        conn = get_db()
        try:
            existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if existing:
                flash('Email already registered. Please log in.', 'error')
                return redirect(url_for('auth.login'))

            conn.execute('''INSERT INTO users (full_name, email, phone, password_hash, role)
                            VALUES (?, ?, ?, ?, 'buyer')''',
                         (full_name, email, phone, generate_password_hash(password)))
            conn.commit()
        finally:
            conn.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db()
        try:
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['role'] = user['role']
            flash(f"Welcome back, {user['full_name']}!", 'success')

            next_page = request.args.get('next')
            if user['role'] == 'admin':
                return redirect(next_page or url_for('admin'))
            return redirect(next_page or url_for('index'))

        flash('Invalid email or password.', 'error')
        return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))