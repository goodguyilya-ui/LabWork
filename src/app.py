import os
import re
import functools
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from flask import (
    Flask, render_template, redirect, url_for,
    request, session, flash, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super-secret-dev-key-change-in-prod')

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DB_CONFIG = {
    'host':     os.getenv('DB_HOST',     'localhost'),
    'port':     os.getenv('DB_PORT',     '5432'),
    'database': os.getenv('DB_NAME',     'venue_db'),
    'user':     os.getenv('DB_USER',     'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
}


@contextmanager
def get_db():
    """Context-manager that yields a psycopg2 connection and auto-commits/rolls back."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Validation regexes
# ---------------------------------------------------------------------------
LOGIN_REGEX = re.compile(r'^[a-zA-Z0-9]{6,}$')
FIO_REGEX   = re.compile(r'^[А-Яа-яЁё\s]+$')
PHONE_REGEX = re.compile(r'^8\(\d{3}\)\d{3}-\d{2}-\d{2}$')
EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------
def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Необходимо войти в систему.', 'error')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Необходимо войти в систему.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({
                'status': 403,
                'error':  'AccessDenied',
                'detail': 'Missing admin privilege',
            }), 403
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ── Registration ─────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        return render_template('register.html')

    login_val    = request.form.get('login', '').strip()
    password_val = request.form.get('password', '').strip()
    full_name    = request.form.get('full_name', '').strip()
    phone        = request.form.get('phone', '').strip()
    email        = request.form.get('email', '').strip()

    field_errors = {}

    if not LOGIN_REGEX.match(login_val):
        field_errors['login'] = 'Логин: только латинские буквы и цифры, не менее 6 символов.'
    if len(password_val) < 8:
        field_errors['password'] = 'Пароль должен содержать не менее 8 символов.'
    if not FIO_REGEX.match(full_name):
        field_errors['full_name'] = 'ФИО должно содержать только кириллицу и пробелы.'
    if not PHONE_REGEX.match(phone):
        field_errors['phone'] = 'Телефон: строго по формату 8(XXX)XXX-XX-XX.'
    if not EMAIL_REGEX.match(email):
        field_errors['email'] = 'Некорректный формат адреса электронной почты.'

    if field_errors:
        return render_template('register.html', field_errors=field_errors, errors=list(field_errors.values()), form=request.form), 400

    try:
        with get_db() as conn:
            cur = conn.cursor()

            # uniqueness checks
            cur.execute('SELECT id FROM users WHERE login = %s', (login_val,))
            if cur.fetchone():
                field_errors['login'] = 'Логин уже занят другим пользователем.'

            cur.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cur.fetchone():
                field_errors['email'] = 'Email уже зарегистрирован в системе.'

            if field_errors:
                return render_template('register.html', field_errors=field_errors, errors=list(field_errors.values()), form=request.form), 400

            pwd_hash = generate_password_hash(password_val)
            cur.execute(
                '''INSERT INTO users (login, password_hash, full_name, phone, email)
                   VALUES (%s, %s, %s, %s, %s)''',
                (login_val, pwd_hash, full_name, phone, email),
            )

    except psycopg2.Error as e:
        app.logger.error('DB error on register: %s', e)
        errors.append('Ошибка базы данных. Попробуйте позже.')
        return render_template('register.html', errors=errors, form=request.form)

    flash('Регистрация прошла успешно! Теперь войдите в систему.', 'success')
    return redirect(url_for('login'))


# ── Login ─────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        return render_template('login.html')

    login_val    = request.form.get('login', '').strip()
    password_val = request.form.get('password', '').strip()

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SELECT * FROM users WHERE login = %s', (login_val,))
            user = cur.fetchone()
    except psycopg2.Error as e:
        app.logger.error('DB error on login: %s', e)
        flash('Ошибка базы данных. Попробуйте позже.', 'error')
        return render_template('login.html')

    if not user or not check_password_hash(user['password_hash'], password_val):
        field_errors = {'login': 'Неверный логин или пароль. Проверьте данные и повторите попытку.'}
        flash('Неверный логин или пароль.', 'error')
        return render_template('login.html', field_errors=field_errors, form=request.form), 400

    session.clear()
    session['user_id']   = user['id']
    session['login']     = user['login']
    session['role']      = user['role']
    session['full_name'] = user['full_name']

    flash(f'Добро пожаловать, {user["full_name"]}!', 'success')

    if user['role'] == 'admin':
        return redirect(url_for('admin_panel'))
    return redirect(url_for('dashboard'))


# ── Logout ────────────────────────────────────────────────────────────────────

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))


# ── Dashboard (personal cabinet) ─────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # user info
            cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
            user = cur.fetchone()

            # venues for dropdown
            cur.execute('SELECT id, name, type, capacity, price_per_hour FROM venues ORDER BY name')
            venues = cur.fetchall()

            # user reservations
            cur.execute(
                '''SELECT r.id, r.start_time, r.end_time, r.payment_method, r.status, r.created_at,
                          v.name AS venue_name,
                          rv.id  AS review_id
                   FROM reservations r
                   JOIN venues v ON v.id = r.venue_id
                   LEFT JOIN reviews rv ON rv.reservation_id = r.id
                   WHERE r.user_id = %s
                   ORDER BY r.created_at DESC''',
                (user_id,),
            )
            reservations = cur.fetchall()

    except psycopg2.Error as e:
        app.logger.error('DB error on dashboard: %s', e)
        flash('Ошибка загрузки данных.', 'error')
        return render_template('dashboard.html', user={}, venues=[], reservations=[])

    return render_template('dashboard.html', user=user, venues=venues, reservations=reservations)


# ── New reservation ───────────────────────────────────────────────────────────

@app.route('/reservation/new', methods=['POST'])
@login_required
def reservation_new():
    venue_id       = request.form.get('venue_id', '').strip()
    start_time     = request.form.get('start_time', '').strip()
    end_time       = request.form.get('end_time', '').strip()
    payment_method = request.form.get('payment_method', '').strip()

    if not all([venue_id, start_time, end_time, payment_method]):
        flash('Заполните все поля заявки.', 'error')
        return redirect(url_for('dashboard'))

    if payment_method not in ('очно', 'СБП'):
        flash('Некорректный способ оплаты.', 'error')
        return redirect(url_for('dashboard'))

    if start_time >= end_time:
        flash('Время начала должно быть раньше времени окончания.', 'error')
        return redirect(url_for('dashboard'))

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                '''INSERT INTO reservations (user_id, venue_id, start_time, end_time, payment_method)
                   VALUES (%s, %s, %s, %s, %s)''',
                (session['user_id'], venue_id, start_time, end_time, payment_method),
            )
    except psycopg2.Error as e:
        app.logger.error('DB error on reservation_new: %s', e)
        flash('Ошибка сохранения заявки. Проверьте данные.', 'error')
        return redirect(url_for('dashboard'))

    flash('Заявка успешно создана!', 'success')
    return redirect(url_for('dashboard'))


# ── Change reservation status (admin) ────────────────────────────────────────

ALLOWED_TRANSITIONS = {
    'Новая':                 'Мероприятие назначено',
    'Мероприятие назначено': 'Завершено',
}


@app.route('/reservation/<int:res_id>/status', methods=['POST'])
@admin_required
def reservation_status(res_id):
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cur.execute('SELECT status FROM reservations WHERE id = %s', (res_id,))
            row = cur.fetchone()

            if not row:
                flash('Заявка не найдена.', 'error')
                return redirect(url_for('admin_panel'))

            current_status = row['status']
            new_status = ALLOWED_TRANSITIONS.get(current_status)

            if new_status is None:
                flash('Смена статуса для этой заявки невозможна.', 'error')
                return redirect(url_for('admin_panel'))

            cur.execute(
                'UPDATE reservations SET status = %s WHERE id = %s',
                (new_status, res_id),
            )

    except psycopg2.Error as e:
        app.logger.error('DB error on status change: %s', e)
        flash('Ошибка обновления статуса.', 'error')
        return redirect(url_for('admin_panel'))

    flash(f'Статус заявки #{res_id} изменён на «{new_status}».', 'success')
    return redirect(url_for('admin_panel'))


# ── Submit review ─────────────────────────────────────────────────────────────

@app.route('/review/new', methods=['POST'])
@login_required
def review_new():
    reservation_id = request.form.get('reservation_id', '').strip()
    rating         = request.form.get('rating', '').strip()
    comment        = request.form.get('comment', '').strip()

    if not reservation_id or not rating:
        flash('Заполните обязательные поля отзыва.', 'error')
        return redirect(url_for('dashboard'))

    try:
        rating = int(rating)
        if not (1 <= rating <= 5):
            raise ValueError
    except ValueError:
        flash('Оценка должна быть от 1 до 5.', 'error')
        return redirect(url_for('dashboard'))

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # fetch reservation and check ownership + status
            cur.execute(
                'SELECT user_id, venue_id, status FROM reservations WHERE id = %s',
                (reservation_id,),
            )
            res = cur.fetchone()

            if not res:
                flash('Заявка не найдена.', 'error')
                return redirect(url_for('dashboard'))

            if res['user_id'] != session['user_id']:
                flash('Вы не можете оставить отзыв на чужую заявку.', 'error')
                return redirect(url_for('dashboard'))

            if res['status'] != 'Завершено':
                flash('Отзыв можно оставить только по завершённой заявке.', 'error')
                return redirect(url_for('dashboard'))

            # check no existing review
            cur.execute(
                'SELECT id FROM reviews WHERE reservation_id = %s',
                (reservation_id,),
            )
            if cur.fetchone():
                flash('Вы уже оставили отзыв на эту заявку.', 'error')
                return redirect(url_for('dashboard'))

            cur.execute(
                '''INSERT INTO reviews (user_id, venue_id, reservation_id, rating, comment)
                   VALUES (%s, %s, %s, %s, %s)''',
                (session['user_id'], res['venue_id'], reservation_id, rating, comment or None),
            )

    except psycopg2.Error as e:
        app.logger.error('DB error on review_new: %s', e)
        flash('Ошибка сохранения отзыва.', 'error')
        return redirect(url_for('dashboard'))

    flash('Спасибо за ваш отзыв!', 'success')
    return redirect(url_for('dashboard'))


# ── Admin panel ───────────────────────────────────────────────────────────────

@app.route('/admin-panel')
@admin_required
def admin_panel():
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                '''SELECT r.id, r.start_time, r.end_time, r.payment_method, r.status, r.created_at,
                          u.full_name, u.phone, u.login,
                          v.name AS venue_name
                   FROM reservations r
                   JOIN users  u ON u.id = r.user_id
                   JOIN venues v ON v.id = r.venue_id
                   ORDER BY r.created_at DESC'''
            )
            reservations = cur.fetchall()
    except psycopg2.Error as e:
        app.logger.error('DB error on admin_panel: %s', e)
        flash('Ошибка загрузки данных.', 'error')
        reservations = []

    return render_template('admin.html', reservations=reservations)


# ── UI-Kit (LR-03 Showcase) ──────────────────────────────────────────────────

@app.route('/uikit')
def uikit():
    return render_template('uikit.html')


# ── Error pages ───────────────────────────────────────────────────────────────

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
