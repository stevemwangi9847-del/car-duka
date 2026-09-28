from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from dotenv import load_dotenv
from libsql_client import create_client_sync

# Load .env BEFORE any os.environ calls
load_dotenv()

auth_bp = Blueprint('auth', __name__)


def get_db():
    return create_client_sync(
        url=os.environ.get("LIBSQL_URL"),
        auth_token=os.environ.get("LIBSQL_AUTH_TOKEN") or None
    )


def init_auth_db():
    """Create users table if it doesn't exist and seed a default admin."""
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'buyer',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Seed default admin if none exists
    result = conn.execute("SELECT * FROM users WHERE role = 'admin'")
    existing_admin = result.rows[0] if result.rows else None
    if not existing_admin:
        conn.execute('''INSERT INTO users (full_name, email, phone, password_hash, role)
                     VALUES (?, ?, ?, ?, ?)''',
                  ['Car Duka Admin',
                   'admin@carduka.com',
                   '0718870024',
                   generate_password_hash('admin123'),
                   'admin'])
        print("[OK] Default admin created: admin@carduka.com / admin123")

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
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form['password']
        confirm = request.form['confirm_password']

        if not full_name or not email or not password:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('auth.register'))

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('auth.register'))

        conn = get_db()
        result = conn.execute('SELECT id FROM users WHERE email = ?', [email])
        existing = result.rows[0] if result.rows else None
        if existing:
            conn.close()
            flash('Email already registered. Please log in.', 'error')
            return redirect(url_for('auth.login'))

        conn.execute('''INSERT INTO users (full_name, email, phone, password_hash, role)
                        VALUES (?, ?, ?, ?, 'buyer')''',
                     [full_name, email, phone, generate_password_hash(password)])
        conn.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_db()
        result = conn.execute('SELECT * FROM users WHERE email = ?', [email])
        user = result.rows[0] if result.rows else None
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
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))
