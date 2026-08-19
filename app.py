# ============================================================
# Web-Based Personal Finance Management System
# Backend: Python (Flask)  |  Database: MySQL
# Frontend: HTML, CSS, JavaScript
# ============================================================

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from functools import wraps
from datetime import datetime, date
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# ── Database ─────────────────────────────────────────────────
def get_db():
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )
    return conn


def init_db():
    """Create database and tables if they don't exist."""
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        autocommit=True
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute(f"USE {config.DB_NAME}")

    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100),
            currency VARCHAR(10) DEFAULT 'KES',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(50) NOT NULL,
            type ENUM('income','expense') NOT NULL,
            color VARCHAR(10) DEFAULT '#6366f1',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            category_id INT,
            type ENUM('income','expense') NOT NULL,
            amount DECIMAL(15,2) NOT NULL,
            description VARCHAR(255),
            transaction_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS budgets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            category_id INT,
            name VARCHAR(100) NOT NULL,
            amount DECIMAL(15,2) NOT NULL,
            month INT,
            year INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS savings_goals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            target_amount DECIMAL(15,2) NOT NULL,
            saved_amount DECIMAL(15,2) DEFAULT 0.00,
            deadline DATE,
            status ENUM('active','completed','paused') DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )"""
    ]
    for sql in tables:
        cur.execute(sql)
    cur.close()
    conn.close()


def seed_categories(user_id):
    """Insert default categories for a new user."""
    conn = get_db()
    cur = conn.cursor()
    defaults = [
        (user_id, 'Salary',           'income',  '#10b981'),
        (user_id, 'Freelance',        'income',  '#06b6d4'),
        (user_id, 'Business',         'income',  '#8b5cf6'),
        (user_id, 'Other Income',     'income',  '#6b7280'),
        (user_id, 'Food & Groceries', 'expense', '#ef4444'),
        (user_id, 'Rent / Housing',   'expense', '#f97316'),
        (user_id, 'Transport',        'expense', '#eab308'),
        (user_id, 'Education',        'expense', '#3b82f6'),
        (user_id, 'Health',           'expense', '#ec4899'),
        (user_id, 'Entertainment',    'expense', '#a855f7'),
        (user_id, 'Utilities',        'expense', '#14b8a6'),
        (user_id, 'Clothing',         'expense', '#f43f5e'),
        (user_id, 'Other Expense',    'expense', '#6b7280'),
    ]
    cur.executemany(
        "INSERT INTO categories (user_id, name, type, color) VALUES (%s,%s,%s,%s)",
        defaults
    )
    cur.close()
    conn.close()


# ── Helpers ──────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def fmt_currency(amount, currency='KES'):
    return f"{currency} {float(amount):,.2f}"


app.jinja_env.globals['fmt_currency'] = fmt_currency
app.jinja_env.globals['now'] = datetime.now


# ══════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password  = request.form.get('password', '')

        if not identifier or not password:
            error = 'Please enter your username/email and password.'
        else:
            conn = get_db()
            cur  = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT * FROM users WHERE username=%s OR email=%s LIMIT 1",
                (identifier, identifier)
            )
            user = cur.fetchone()
            cur.close(); conn.close()

            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['full_name']  = user['full_name'] or user['username']
                session['email'] = user['email']
                session['currency'] = user['currency']
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid username/email or password.'

    return render_template('auth/login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    error   = None
    success = None

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username  = request.form.get('username', '').strip()
        email     = request.form.get('email', '').strip()
        password  = request.form.get('password', '')
        confirm   = request.form.get('confirm', '')
        currency  = request.form.get('currency', 'KES')

        import re
        if not all([full_name, username, email, password]):
            error = 'All fields are required.'
        elif not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            error = 'Username must be 3–30 characters (letters, numbers, underscore).'
        elif '@' not in email:
            error = 'Please enter a valid email address.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        else:
            conn = get_db()
            cur  = conn.cursor(dictionary=True)
            cur.execute("SELECT id FROM users WHERE username=%s OR email=%s LIMIT 1", (username, email))
            if cur.fetchone():
                error = 'Username or email is already registered.'
            else:
                pw_hash = generate_password_hash(password)
                cur.execute(
                    "INSERT INTO users (full_name, username, email, password_hash, currency) VALUES (%s,%s,%s,%s,%s)",
                    (full_name, username, email, pw_hash, currency)
                )
                new_id = cur.lastrowid
                cur.close(); conn.close()
                seed_categories(new_id)
                success = 'Account created! You can now sign in.'

            if not success:
                cur.close(); conn.close()

    return render_template('auth/register.html', error=error, success=success)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
def dashboard():
    uid      = session['user_id']
    currency = session['currency']
    month    = datetime.now().month
    year     = datetime.now().year

    conn = get_db()
    cur  = conn.cursor(dictionary=True)

    # Monthly totals
    cur.execute("""
        SELECT
            SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS total_income,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS total_expense
        FROM transactions
        WHERE user_id=%s AND MONTH(transaction_date)=%s AND YEAR(transaction_date)=%s
    """, (uid, month, year))
    monthly = cur.fetchone()
    total_income  = float(monthly['total_income']  or 0)
    total_expense = float(monthly['total_expense'] or 0)
    balance       = total_income - total_expense

    # All-time savings
    cur.execute("""
        SELECT SUM(saved_amount) AS saved, COUNT(*) AS cnt
        FROM savings_goals WHERE user_id=%s AND status='active'
    """, (uid,))
    sav = cur.fetchone()

    # Recent 6 transactions
    cur.execute("""
        SELECT t.*, c.name AS cat_name, c.color AS cat_color
        FROM transactions t
        LEFT JOIN categories c ON t.category_id=c.id
        WHERE t.user_id=%s
        ORDER BY t.transaction_date DESC, t.created_at DESC LIMIT 6
    """, (uid,))
    recent_tx = cur.fetchall()

    # 6-month trend
    trend = []
    for i in range(5, -1, -1):
        import calendar
        m = (month - i - 1) % 12 + 1
        y = year - ((month - i - 1) // 12 + (1 if (month - i - 1) < 0 else 0))
        cur.execute("""
            SELECT SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS inc,
                   SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS exp
            FROM transactions WHERE user_id=%s AND MONTH(transaction_date)=%s AND YEAR(transaction_date)=%s
        """, (uid, m, y))
        row = cur.fetchone()
        trend.append({
            'label': datetime(y, m, 1).strftime('%b'),
            'inc':   float(row['inc'] or 0),
            'exp':   float(row['exp'] or 0),
        })

    # Category expenses this month
    cur.execute("""
        SELECT c.name, SUM(t.amount) AS total, c.color
        FROM transactions t JOIN categories c ON t.category_id=c.id
        WHERE t.user_id=%s AND t.type='expense'
          AND MONTH(t.transaction_date)=%s AND YEAR(t.transaction_date)=%s
        GROUP BY c.id ORDER BY total DESC LIMIT 6
    """, (uid, month, year))
    cat_expenses = cur.fetchall()

    # Budgets
    cur.execute("""
        SELECT b.*, c.name AS cat_name,
            COALESCE((SELECT SUM(amount) FROM transactions
                WHERE user_id=%s AND category_id=b.category_id
                  AND type='expense' AND MONTH(transaction_date)=%s AND YEAR(transaction_date)=%s
            ), 0) AS spent
        FROM budgets b LEFT JOIN categories c ON b.category_id=c.id
        WHERE b.user_id=%s AND b.month=%s AND b.year=%s
        ORDER BY b.created_at DESC LIMIT 5
    """, (uid, month, year, uid, month, year))
    budgets = cur.fetchall()

    cur.close(); conn.close()

    return render_template('dashboard.html',
        total_income=total_income, total_expense=total_expense,
        balance=balance, savings=sav, recent_tx=recent_tx,
        trend=trend, cat_expenses=cat_expenses, budgets=budgets,
        month_name=datetime.now().strftime('%B %Y')
    )


# ══════════════════════════════════════════════════════════════
# TRANSACTIONS
# ══════════════════════════════════════════════════════════════

@app.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    uid      = session['user_id']
    currency = session['currency']

    if request.method == 'POST':
        tx_id       = int(request.form.get('id', 0))
        tx_type     = request.form.get('type', 'expense')
        amount      = float(request.form.get('amount', 0))
        category_id = request.form.get('category_id') or None
        description = request.form.get('description', '').strip()
        tx_date     = request.form.get('transaction_date', date.today().isoformat())

        if amount <= 0:
            flash('Amount must be greater than zero.', 'error')
            return redirect(url_for('transactions'))

        conn = get_db()
        cur  = conn.cursor()
        if tx_id:
            cur.execute("""
                UPDATE transactions SET type=%s,amount=%s,category_id=%s,description=%s,transaction_date=%s
                WHERE id=%s AND user_id=%s
            """, (tx_type, amount, category_id, description, tx_date, tx_id, uid))
        else:
            cur.execute("""
                INSERT INTO transactions (user_id,type,amount,category_id,description,transaction_date)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (uid, tx_type, amount, category_id, description, tx_date))
        cur.close(); conn.close()
        flash('Transaction saved.', 'success')
        return redirect(url_for('transactions'))

    # DELETE
    if request.args.get('delete'):
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (int(request.args['delete']), uid))
        cur.close(); conn.close()
        flash('Transaction deleted.', 'success')
        return redirect(url_for('transactions'))

    # Filters
    filter_type  = request.args.get('type', '')
    filter_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    fy, fm = filter_month.split('-') if '-' in filter_month else (datetime.now().year, datetime.now().month)

    query  = "SELECT t.*, c.name AS cat_name, c.color AS cat_color FROM transactions t LEFT JOIN categories c ON t.category_id=c.id WHERE t.user_id=%s"
    params = [uid]
    if filter_type:
        query += " AND t.type=%s"; params.append(filter_type)
    if fy and fm:
        query += " AND YEAR(t.transaction_date)=%s AND MONTH(t.transaction_date)=%s"
        params += [int(fy), int(fm)]
    query += " ORDER BY t.transaction_date DESC, t.created_at DESC"

    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    txs = cur.fetchall()

    # Edit fetch
    edit_tx = None
    if request.args.get('edit'):
        cur.execute("SELECT * FROM transactions WHERE id=%s AND user_id=%s", (int(request.args['edit']), uid))
        edit_tx = cur.fetchone()

    cur.execute("SELECT * FROM categories WHERE user_id=%s ORDER BY type, name", (uid,))
    categories = cur.fetchall()
    cur.close(); conn.close()

    total_inc = sum(float(t['amount']) for t in txs if t['type'] == 'income')
    total_exp = sum(float(t['amount']) for t in txs if t['type'] == 'expense')

    return render_template('transactions.html',
        transactions=txs, categories=categories,
        edit_tx=edit_tx, filter_type=filter_type, filter_month=filter_month,
        total_inc=total_inc, total_exp=total_exp,
        show_modal=bool(request.args.get('add') or edit_tx)
    )


# ══════════════════════════════════════════════════════════════
# BUDGETS
# ══════════════════════════════════════════════════════════════

@app.route('/budget', methods=['GET', 'POST'])
@login_required
def budget():
    uid   = session['user_id']
    month_str = request.args.get('month', str(datetime.now().month))
    year_str = request.args.get('year', str(datetime.now().year))

    month = int(month_str.split('?')[0])
    year = int(year_str.split('?')[0])
    
    if request.method == 'POST':
        b_id        = int(request.form.get('id', 0))
        name        = request.form.get('name', '').strip()
        amount      = float(request.form.get('amount', 0))
        category_id = request.form.get('category_id') or None
        b_month     = int(request.form.get('month', month))
        b_year      = int(request.form.get('year',  year))

        if not name or amount <= 0:
            flash('Name and a positive amount are required.', 'error')
            return redirect(url_for('budget'))

        conn = get_db(); cur = conn.cursor()
        if b_id:
            cur.execute("UPDATE budgets SET name=%s,amount=%s,category_id=%s,month=%s,year=%s WHERE id=%s AND user_id=%s",
                (name, amount, category_id, b_month, b_year, b_id, uid))
        else:
            cur.execute("INSERT INTO budgets (user_id,name,amount,category_id,month,year) VALUES (%s,%s,%s,%s,%s,%s)",
                (uid, name, amount, category_id, b_month, b_year))
        cur.close(); conn.close()
        flash('Budget saved.', 'success')
        return redirect(url_for('budget', month=b_month, year=b_year))

    if request.args.get('delete'):
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM budgets WHERE id=%s AND user_id=%s", (int(request.args['delete']), uid))
        cur.close(); conn.close()
        flash('Budget deleted.', 'success')
        return redirect(url_for('budget', month=month, year=year))

    conn = get_db(); cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT b.*, c.name AS cat_name,
            COALESCE((SELECT SUM(amount) FROM transactions
                WHERE user_id=%s AND category_id=b.category_id
                  AND type='expense' AND MONTH(transaction_date)=%s AND YEAR(transaction_date)=%s
            ), 0) AS spent
        FROM budgets b LEFT JOIN categories c ON b.category_id=c.id
        WHERE b.user_id=%s AND b.month=%s AND b.year=%s
        ORDER BY b.created_at DESC
    """, (uid, month, year, uid, month, year))
    budgets = cur.fetchall()

    edit_b = None
    if request.args.get('edit'):
        cur.execute("SELECT * FROM budgets WHERE id=%s AND user_id=%s", (int(request.args['edit']), uid))
        edit_b = cur.fetchone()

    cur.execute("SELECT * FROM categories WHERE user_id=%s AND type='expense' ORDER BY name", (uid,))
    categories = cur.fetchall()
    cur.close(); conn.close()

    for b in budgets:
        b['spent']   = float(b['spent'])
        b['amount']  = float(b['amount'])
        b['pct']     = min(100, round(b['spent'] / b['amount'] * 100)) if b['amount'] > 0 else 0
        b['remaining'] = b['amount'] - b['spent']

    return render_template('budget.html',
        budgets=budgets, categories=categories, edit_b=edit_b,
        month=month, year=year,
        show_modal=bool(request.args.get('add') or edit_b),
        month_name=datetime(year, month, 1).strftime('%B %Y')
    )


# ══════════════════════════════════════════════════════════════
# SAVINGS GOALS
# ══════════════════════════════════════════════════════════════

@app.route('/savings', methods=['GET', 'POST'])
@login_required
def savings():
    uid = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'fund':
            goal_id = int(request.form.get('goal_id'))
            extra   = float(request.form.get('extra_amount', 0))
            if extra > 0:
                conn = get_db(); cur = conn.cursor()
                cur.execute("""
                    UPDATE savings_goals
                    SET saved_amount = LEAST(saved_amount + %s, target_amount),
                        status = IF(saved_amount + %s >= target_amount, 'completed', status)
                    WHERE id=%s AND user_id=%s
                """, (extra, extra, goal_id, uid))
                cur.close(); conn.close()
            flash('Funds added.', 'success')
            return redirect(url_for('savings'))

        g_id     = int(request.form.get('id', 0))
        name     = request.form.get('name', '').strip()
        target   = float(request.form.get('target', 0))
        saved    = float(request.form.get('saved', 0))
        deadline = request.form.get('deadline') or None
        status   = request.form.get('status', 'active')

        if not name or target <= 0:
            flash('Name and a positive target are required.', 'error')
            return redirect(url_for('savings'))

        conn = get_db(); cur = conn.cursor()
        if g_id:
            cur.execute("UPDATE savings_goals SET name=%s,target_amount=%s,saved_amount=%s,deadline=%s,status=%s WHERE id=%s AND user_id=%s",
                (name, target, saved, deadline, status, g_id, uid))
        else:
            cur.execute("INSERT INTO savings_goals (user_id,name,target_amount,saved_amount,deadline) VALUES (%s,%s,%s,%s,%s)",
                (uid, name, target, saved, deadline))
        cur.close(); conn.close()
        flash('Savings goal saved.', 'success')
        return redirect(url_for('savings'))

    if request.args.get('delete'):
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM savings_goals WHERE id=%s AND user_id=%s", (int(request.args['delete']), uid))
        cur.close(); conn.close()
        flash('Goal deleted.', 'success')
        return redirect(url_for('savings'))

    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM savings_goals WHERE user_id=%s ORDER BY status, created_at DESC", (uid,))
    goals = cur.fetchall()

    edit_g = None
    if request.args.get('edit'):
        cur.execute("SELECT * FROM savings_goals WHERE id=%s AND user_id=%s", (int(request.args['edit']), uid))
        edit_g = cur.fetchone()
    cur.close(); conn.close()

    for g in goals:
        g['target_amount'] = float(g['target_amount'])
        g['saved_amount']  = float(g['saved_amount'])
        g['pct'] = min(100, round(g['saved_amount'] / g['target_amount'] * 100)) if g['target_amount'] > 0 else 0
        g['remaining'] = max(0, g['target_amount'] - g['saved_amount'])
        if g['deadline']:
            delta = (g['deadline'] - date.today()).days
            g['days_left'] = max(0, delta)
        else:
            g['days_left'] = None

    return render_template('savings.html', goals=goals, edit_g=edit_g,
        show_modal=bool(request.args.get('add') or edit_g))


# ══════════════════════════════════════════════════════════════
# REPORTS
# ══════════════════════════════════════════════════════════════

@app.route('/reports')
@login_required
def reports():
    uid         = session['user_id']
    filter_year = int(request.args.get('year', datetime.now().year))

    conn = get_db(); cur = conn.cursor(dictionary=True)

    monthly_data = []
    for m in range(1, 13):
        cur.execute("""
            SELECT SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS inc,
                   SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS exp
            FROM transactions WHERE user_id=%s AND MONTH(transaction_date)=%s AND YEAR(transaction_date)=%s
        """, (uid, m, filter_year))
        row = cur.fetchone()
        monthly_data.append({
            'month': datetime(filter_year, m, 1).strftime('%b'),
            'inc':   float(row['inc'] or 0),
            'exp':   float(row['exp'] or 0),
        })

    cur.execute("""
        SELECT c.name, c.color, SUM(t.amount) AS total
        FROM transactions t JOIN categories c ON t.category_id=c.id
        WHERE t.user_id=%s AND t.type='income' AND YEAR(t.transaction_date)=%s
        GROUP BY c.id ORDER BY total DESC
    """, (uid, filter_year))
    income_by_cat = cur.fetchall()

    cur.execute("""
        SELECT c.name, c.color, SUM(t.amount) AS total
        FROM transactions t JOIN categories c ON t.category_id=c.id
        WHERE t.user_id=%s AND t.type='expense' AND YEAR(t.transaction_date)=%s
        GROUP BY c.id ORDER BY total DESC
    """, (uid, filter_year))
    expense_by_cat = cur.fetchall()

    cur.execute("""
        SELECT t.*, c.name AS cat_name FROM transactions t
        LEFT JOIN categories c ON t.category_id=c.id
        WHERE t.user_id=%s AND t.type='expense' AND YEAR(t.transaction_date)=%s
        ORDER BY t.amount DESC LIMIT 5
    """, (uid, filter_year))
    top_expenses = cur.fetchall()
    cur.close(); conn.close()

    total_inc = sum(m['inc'] for m in monthly_data)
    total_exp = sum(m['exp'] for m in monthly_data)
    net       = total_inc - total_exp
    rate      = round(net / total_inc * 100) if total_inc > 0 else 0

    return render_template('reports.html',
        monthly_data=monthly_data, income_by_cat=income_by_cat,
        expense_by_cat=expense_by_cat, top_expenses=top_expenses,
        total_inc=total_inc, total_exp=total_exp, net=net, rate=rate,
        filter_year=filter_year
    )


# ══════════════════════════════════════════════════════════════
# PROFILE
# ══════════════════════════════════════════════════════════════

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    uid = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'profile':
            full_name = request.form.get('full_name', '').strip()
            email     = request.form.get('email', '').strip()
            currency  = request.form.get('currency', 'KES')
            if not full_name or not email:
                flash('Name and email are required.', 'error')
            else:
                conn = get_db(); cur = conn.cursor()
                cur.execute("UPDATE users SET full_name=%s,email=%s,currency=%s WHERE id=%s",
                    (full_name, email, currency, uid))
                cur.close(); conn.close()
                session['full_name'] = full_name
                session['email']     = email
                session['currency']  = currency
                flash('Profile updated.', 'success')

        elif action == 'password':
            current = request.form.get('current_password', '')
            new_pw  = request.form.get('new_password', '')
            confirm = request.form.get('confirm_password', '')

            conn = get_db(); cur = conn.cursor(dictionary=True)
            cur.execute("SELECT password_hash FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()

            if not check_password_hash(row['password_hash'], current):
                flash('Current password is incorrect.', 'error')
            elif len(new_pw) < 6:
                flash('New password must be at least 6 characters.', 'error')
            elif new_pw != confirm:
                flash('Passwords do not match.', 'error')
            else:
                cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                    (generate_password_hash(new_pw), uid))
                flash('Password changed.', 'success')
            cur.close(); conn.close()

        return redirect(url_for('profile'))

    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
    user_data = cur.fetchone()
    cur.execute("""
        SELECT COUNT(*) AS tx_count,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS total_income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS total_expense,
               MIN(transaction_date) AS first_tx
        FROM transactions WHERE user_id=%s
    """, (uid,))
    stats = cur.fetchone()
    cur.close(); conn.close()

    return render_template('profile.html', user_data=user_data, stats=stats)


# ── Entry point ───────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
