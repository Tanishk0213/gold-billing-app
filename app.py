from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from datetime import date
from random import randint
from flask import flash
import re

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "gold_shop_secret_2026")

# MySQL Connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=os.getenv("DB_PASSWORD"),
    database="gold_shop"
)
cursor = db.cursor()

# Helper Functions
otp_store = {}

def is_indian_number(mobile):
    pattern = r'^(\+91)?[6-9]\d{9}$'
    match = re.match(pattern, mobile)
    if match:
        if mobile.startswith('+91'):
            return len(mobile[3:]) == 10
        return len(mobile) == 10
    return False

def normalize_mobile(mobile):
    mobile = mobile.strip()
    if mobile.startswith('0'):
        return '+91' + mobile[1:]
    elif not mobile.startswith('+91'):
        return '+91' + mobile
    return mobile

# ROUTES
@app.route('/')
def home():
    if 'user' in session:
        return redirect('/view')
    return redirect('/login')

@app.route('/register', methods=['GET','POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        mobile = normalize_mobile(request.form['mobile'].strip())
        email = request.form['email'].strip()

        if not is_indian_number(mobile):
            error = "Invalid mobile number"
            return render_template("register.html", error=error)

        if password != confirm_password:
            error = "Passwords do not match"
            return render_template("register.html", error=error)

        cursor.execute("SELECT * FROM users WHERE username=%s OR email=%s", (username, email))
        if cursor.fetchone():
            error = "Username or Email already exists!"
            return render_template("register.html", error=error)

        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password, mobile, email) VALUES (%s, %s, %s, %s)", 
                       (username, hashed_password, mobile, email))
        db.commit()
        flash("Registration successful!", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        if user and check_password_hash(user[2], password):
            session['user'] = username
            return redirect('/view')
        else:
            error = "Invalid username or password"
            return render_template("login.html", error=error)
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# --- UPDATED VIEW FUNCTION ---
@app.route('/view')
def view():
    if 'user' not in session:
        return redirect('/login')

    # Category column serthu select panrom
    cursor.execute("""
        SELECT id, date, category, gold_type, rate, gst, making 
        FROM gold_rates
        WHERE is_deleted = 0
        ORDER BY date DESC, category ASC
    """)
    data = cursor.fetchall()
    return render_template("view.html", rates=data, user=session['user'])

@app.route('/add')
def add_gold_page():
    today = date.today().strftime("%Y-%m-%d")
    return render_template("add.html", today=today)

# --- UPDATED SAVE FUNCTION ---
@app.route('/save', methods=['POST'])
def save():
    if 'user' not in session:
        return redirect('/login')

    date_val = request.form['date']
    category = request.form['category']  # New Field
    gold_type = request.form['gold_type']
    rate = request.form['rate']
    gst = request.form['gst']
    making = request.form['making']

    cursor.execute(
        "INSERT INTO gold_rates (date, category, gold_type, rate, gst, making) VALUES (%s,%s,%s,%s,%s,%s)",
        (date_val, category, gold_type, rate, gst, making)
    )
    db.commit()
    return redirect('/view')

# --- UPDATED UPDATE FUNCTION ---
# --- UPDATED UPDATE FUNCTION ---
@app.route('/update_today', methods=['POST'])
def update_today():
    date_val = request.form.get('edit_date')
    category = request.form.get('edit_category')
    gold_type = request.form.get('edit_gold_type')
    new_rate = request.form.get('new_rate')
    new_gst = request.form.get('new_gst')
    new_making = request.form.get('new_making')

    cursor.execute("""
        UPDATE gold_rates
        SET rate=%s, gst=%s, making=%s
        WHERE date=%s AND category=%s AND gold_type=%s AND is_deleted=0
    """, (new_rate, new_gst, new_making, date_val, category, gold_type))

    db.commit()

    if cursor.rowcount == 0:
        # Data illana Error message
        flash(f"{category} data not found for today!", "error")
        return redirect('/add') # Inga thaan theliva /add page-ku poga solrom
    else:
        # Success aagiducha View page-ku pogum
        flash(f"{category} rate updated successfully!", "success")
        return redirect('/view')

# Reset Password Routes (Same as before)
@app.route('/reset_password', methods=['GET','POST'])
def reset_password():
    otp_sent = False
    contact = None
    error = None
    if request.method == 'POST':
        contact = request.form['contact'].strip()
        contact = normalize_mobile(contact)
        
        cursor.execute("SELECT * FROM users WHERE email=%s OR mobile=%s", (contact, contact))
        user = cursor.fetchone()
        if not user:
            error = "Invalid number!"
            return render_template("reset_password.html", error=error, contact=contact)

        if 'otp' in request.form:
            entered_otp = request.form['otp']
            new_pass = request.form['new_password']
            confirm_pass = request.form['confirm_password']
            if str(otp_store.get(contact)) != entered_otp:
                error = "Invalid OTP"
                otp_sent = True
                return render_template("reset_password.html", error=error, contact=contact, otp_sent=otp_sent)
            if new_pass != confirm_pass:
                error = "Mismatch password"
                otp_sent = True
                return render_template("reset_password.html", error=error, contact=contact, otp_sent=otp_sent)
            
            hashed = generate_password_hash(new_pass)
            cursor.execute("UPDATE users SET password=%s WHERE email=%s OR mobile=%s", (hashed, contact, contact))
            db.commit()
            otp_store.pop(contact, None)
            flash("Password reset successful!", "success")
            return redirect(url_for('login'))
        
        otp = randint(100000, 999999)
        otp_store[contact] = otp
        otp_sent = True
        print(f"OTP: {otp}")
        
    return render_template("reset_password.html", otp_sent=otp_sent, contact=contact)

if __name__ == '__main__':
    app.run(debug=True)