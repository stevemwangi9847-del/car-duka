from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from auth import auth_bp, init_auth_db, login_required, admin_required
import os
from dotenv import load_dotenv
from libsql_client import create_client_sync
import uuid
import re

# Load .env BEFORE any os.environ calls
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "car_duka_secret_key_2024")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

WHATSAPP_NUMBER = "254718870024"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register the auth blueprint
app.register_blueprint(auth_bp)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


from database import get_db


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        make TEXT NOT NULL,
        model TEXT NOT NULL,
        year INTEGER NOT NULL,
        price REAL NOT NULL,
        mileage INTEGER,
        fuel_type TEXT,
        transmission TEXT,
        color TEXT,
        body_type TEXT,
        engine_size TEXT,
        condition TEXT,
        description TEXT,
        image TEXT,
        status TEXT DEFAULT 'available',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        car_id INTEGER NOT NULL,
        user_id INTEGER,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        booking_date TEXT NOT NULL,
        booking_time TEXT NOT NULL,
        message TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (car_id) REFERENCES cars (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    conn.close()


_db_initialized = False


@app.before_request
def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            init_auth_db()
            _db_initialized = True
        except Exception as e:
            print(f"Lazy DB initialization warning: {e}")


@app.context_processor
def inject_globals():
    return {
        'whatsapp_number': WHATSAPP_NUMBER,
        'current_user': {
            'id': session.get('user_id'),
            'name': session.get('user_name'),
            'role': session.get('role')
        } if 'user_id' in session else None
    }


# ---------- Public routes ----------
@app.route('/')
def index():
    cars = []
    try:
        conn = get_db()
        cars = conn.execute('SELECT * FROM cars WHERE status = "available" ORDER BY created_at DESC LIMIT 6').rows
        conn.close()
    except Exception as e:
        print(f"Error fetching cars for homepage: {e}")
    return render_template('index.html', cars=cars)


@app.route('/cars')
def cars():
    make = request.args.get('make', '').strip()
    model = request.args.get('model', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    fuel_type = request.args.get('fuel_type', '').strip()
    transmission = request.args.get('transmission', '').strip()
    body_type = request.args.get('body_type', '').strip()
    year = request.args.get('year', '').strip()

    query = 'SELECT * FROM cars WHERE status = "available"'
    params = []

    if make:
        query += ' AND make LIKE ?'; params.append(f'%{make}%')
    if model:
        query += ' AND model LIKE ?'; params.append(f'%{model}%')
    if min_price:
        query += ' AND price >= ?'; params.append(float(min_price))
    if max_price:
        query += ' AND price <= ?'; params.append(float(max_price))
    if fuel_type:
        query += ' AND fuel_type = ?'; params.append(fuel_type)
    if transmission:
        query += ' AND transmission = ?'; params.append(transmission)
    if body_type:
        query += ' AND body_type = ?'; params.append(body_type)
    if year:
        query += ' AND year >= ?'; params.append(int(year))

    query += ' ORDER BY created_at DESC'
    cars = []
    try:
        conn = get_db()
        cars = conn.execute(query, params).rows
        conn.close()
    except Exception as e:
        print(f"Error fetching cars: {e}")
    return render_template('cars.html', cars=cars)


@app.route('/car/<int:car_id>')
def car_detail(car_id):
    conn = get_db()
    result = conn.execute('SELECT * FROM cars WHERE id = ?', [car_id])
    car = result.rows[0] if result.rows else None
    conn.close()
    if car is None:
        flash('Car not found', 'error')
        return redirect(url_for('cars'))
    return render_template('car_detail.html', car=car)


# ---------- Protected buyer route ----------
@app.route('/book/<int:car_id>', methods=['GET', 'POST'])
@login_required
def book(car_id):
    conn = get_db()
    result = conn.execute('SELECT * FROM cars WHERE id = ?', [car_id])
    car = result.rows[0] if result.rows else None
    if car is None:
        conn.close()
        flash('Car not found', 'error')
        return redirect(url_for('cars'))

    if request.method == 'POST':
        conn.execute('''INSERT INTO bookings 
            (car_id, user_id, customer_name, customer_email, customer_phone, booking_date, booking_time, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            [car_id, session['user_id'],
             request.form['customer_name'], request.form['customer_email'],
             request.form['customer_phone'], request.form['booking_date'],
             request.form['booking_time'], request.form.get('message', '')])
        conn.close()
        flash('Booking submitted successfully! We will contact you soon.', 'success')
        return redirect(url_for('car_detail', car_id=car_id))

    conn.close()
    return render_template('booking.html', car=car)


# ---------- Admin routes (protected) ----------
@app.route('/admin')
@admin_required
def admin():
    conn = get_db()
    cars = conn.execute('SELECT * FROM cars ORDER BY created_at DESC').rows
    bookings = conn.execute('''SELECT bookings.*, cars.make, cars.model 
        FROM bookings JOIN cars ON bookings.car_id = cars.id 
        ORDER BY bookings.created_at DESC''').rows
    conn.close()
    return render_template('admin.html', cars=cars, bookings=bookings)


@app.route('/admin/add_car', methods=['GET', 'POST'])
@admin_required
def add_car():
    if request.method == 'POST':
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                image_filename = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        conn = get_db()
        conn.execute('''INSERT INTO cars 
            (make, model, year, price, mileage, fuel_type, transmission, color, body_type, engine_size, condition, description, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            [request.form['make'], request.form['model'], request.form['year'],
             request.form['price'], request.form.get('mileage', 0),
             request.form['fuel_type'], request.form['transmission'],
             request.form.get('color', ''), request.form.get('body_type', ''),
             request.form.get('engine_size', ''), request.form.get('condition', 'Used'),
             request.form.get('description', ''), image_filename])
        conn.close()
        flash('Car added successfully!', 'success')
        return redirect(url_for('admin'))

    return render_template('add_car.html')


@app.route('/admin/delete_car/<int:car_id>')
@admin_required
def delete_car(car_id):
    conn = get_db()
    result = conn.execute('SELECT image FROM cars WHERE id = ?', [car_id])
    car = result.rows[0] if result.rows else None
    if car and car['image']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], car['image']))
        except Exception:
            pass
    conn.execute('DELETE FROM cars WHERE id = ?', [car_id])
    conn.close()
    flash('Car deleted successfully!', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/update_booking/<int:booking_id>/<status>')
@admin_required
def update_booking(booking_id, status):
    conn = get_db()
    conn.execute('UPDATE bookings SET status = ? WHERE id = ?', [status, booking_id])
    conn.close()
    flash('Booking status updated!', 'success')
    return redirect(url_for('admin'))


# ---------- AI chatbot (unchanged) ----------
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    message = data.get('message', '').lower().strip()

    conn = get_db()
    cars = conn.execute('SELECT make, model, year, price FROM cars WHERE status = "available"').rows
    conn.close()

    cars_list = [f"• {c['year']} {c['make']} {c['model']} — KSh {c['price']:,.0f}" for c in cars]
    cars_text = "\n".join(cars_list) if cars_list else "No cars currently available."

    def has(*words):
        return any(w in message for w in words)

    if has('hello', 'hi ', 'hey', 'habari', 'mambo', 'niaje') or message in ('hi', 'hey'):
        reply = ("Hello! 👋 Welcome to **Car Duka**.\n\n"
                 "I can help with:\n• Available cars\n• Prices\n• Booking a viewing\n"
                 "• Contact info\n\nWhat would you like to know?")
    elif has('available', 'cars do you', 'stock', 'show me', 'list', 'vehicles', 'what cars'):
        reply = f"Here are our available cars 🚗:\n\n{cars_text}"
    elif has('price', 'cost', 'how much', 'bei', 'cheap', 'expensive'):
        reply = "Our prices vary by car. 💰 Filter by price on the **Cars** page or tell me a budget!"
    elif has('book', 'booking', 'appointment', 'view', 'test drive', 'schedule'):
        reply = ("To book a viewing 📅:\n1. Log in or Register\n2. Browse the **Cars** page\n"
                 "3. Click **Book Viewing**\n4. Choose a date & time\n\nWe'll confirm via WhatsApp!")
    elif has('register', 'sign up', 'signup', 'account'):
        reply = "To register, click **Login** in the top menu, then **Register**. It takes less than a minute! 📝"
    elif has('login', 'log in', 'sign in', 'signin'):
        reply = "Click **Login** in the top menu to sign in. New here? Choose **Register**. 🔐"
    elif has('contact', 'phone', 'call', 'whatsapp', 'reach', 'number'):
        reply = "📞 Reach us on WhatsApp: **0718870024**\n\nClick the green WhatsApp button!"
    elif has('location', 'where', 'address', 'shop'):
        reply = "📍 We're located in Kenya. Contact us on WhatsApp **0718870024** for directions."
    elif has('payment', 'pay', 'mpesa', 'm-pesa', 'installment', 'loan'):
        reply = "💳 We accept M-Pesa and bank transfers. Contact us on WhatsApp **0718870024** for financing."
    elif has('fuel', 'petrol', 'diesel', 'hybrid', 'electric'):
        reply = "⛽ We have petrol, diesel, and hybrid cars. Filter by fuel type on the **Cars** page."
    elif has('thank', 'asante', 'thanks'):
        reply = "You're welcome! 😊 Karibu tena Car Duka!"
    elif has('bye', 'goodbye', 'kwaheri'):
        reply = "Goodbye! 👋 Drive safe!"
    else:
        reply = ("I'm not sure about that. 🤔 Try:\n• 'What cars do you have?'\n"
                 "• 'Show me cars under 1 million'\n• 'How do I book a viewing?'\n• 'What's your contact?'")

    return jsonify({'reply': reply})


if __name__ == '__main__':
    app.run(debug=True)
