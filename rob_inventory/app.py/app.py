import os
import sqlite3
import psycopg2
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "Rob_autoparts_secret_key_2026")

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, inicia sesión para acceder al sistema."
login_manager.login_message_category = "warning"

# Configurar Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        conn = sqlite3.connect("inventario.db")
        conn.row_factory = sqlite3.Row
        return conn

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (int(user_id),))
    else:
        cursor.execute("SELECT * FROM usuarios WHERE id = ?", (int(user_id),))
    u = cursor.fetchone()
    conn.close()
    if u:
        uid = u[0] if isinstance(u, tuple) else u['id']
        uname = u[1] if isinstance(u, tuple) else u['username']
        upass = u[2] if isinstance(u, tuple) else u['password']
        return User(uid, uname, upass)
    return None

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS productos (
                id SERIAL PRIMARY KEY,
                codigo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                marca TEXT,
                compatibilidad TEXT,
                precio REAL NOT NULL,
                stock INTEGER NOT NULL,
                imagen TEXT
            );
            CREATE TABLE IF NOT EXISTS ventas (
                id SERIAL PRIMARY KEY,
                producto_id INTEGER,
                nombre TEXT,
                cantidad INTEGER,
                total REAL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                marca TEXT,
                compatibilidad TEXT,
                precio REAL NOT NULL,
                stock INTEGER NOT NULL,
                imagen TEXT
            );
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER,
                nombre TEXT,
                cantidad INTEGER,
                total REAL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    count = cursor.fetchone()[0]
    if count == 0:
        hashed_pw = generate_password_hash("admin123")
        if DATABASE_URL:
            cursor.execute("INSERT INTO usuarios (username, password) VALUES (%s, %s)", ("admin", hashed_pw))
        else:
            cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", ("admin", hashed_pw))

    conn.commit()
    conn.close()

init_db()

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
        
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()
        if DATABASE_URL:
            cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        else:
            cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
        
        u = cursor.fetchone()
        conn.close()

        if u:
            uid = u[0] if isinstance(u, tuple) else u['id']
            uname = u[1] if isinstance(u, tuple) else u['username']
            upass = u[2] if isinstance(u, tuple) else u['password']

            if check_password_hash(upass, password):
                user_obj = User(uid, uname, upass)
                login_user(user_obj)
                return redirect(url_for("index"))

        flash("Usuario o contraseña incorrectos.", "danger")
        
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión exitosamente.", "info")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    query = request.args.get("q", "").strip()
    conn = get_db()
    cursor = conn.cursor()
    
    if query:
        q_filter = f"%{query}%"
        if DATABASE_URL:
            cursor.execute("""
                SELECT * FROM productos 
                WHERE codigo ILIKE %s OR nombre ILIKE %s OR marca ILIKE %s OR compatibilidad ILIKE %s
            """, (q_filter, q_filter, q_filter, q_filter))
        else:
            cursor.execute("""
                SELECT * FROM productos 
                WHERE codigo LIKE ? OR nombre LIKE ? OR marca LIKE ? OR compatibilidad LIKE ?
            """, (q_filter, q_filter, q_filter, q_filter))
    else:
        cursor.execute("SELECT * FROM productos")
        
    productos = cursor.fetchall()
    conn.close()
    return render_template("inventario.html", productos=productos, query=query)

@app.route("/agregar", methods=["POST"])
@login_required
def agregar():
    codigo = request.form["codigo"]
    nombre = request.form["nombre"]
    marca = request.form["marca"]
    compatibilidad = request.form["compatibilidad"]
    precio = float(request.form["precio"])
    stock = int(request.form["stock"])
    
    image_url = ""
    if 'imagen' in request.files:
        file = request.files['imagen']
        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file)
            image_url = upload_result.get("secure_url")

    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            INSERT INTO productos (codigo, nombre, marca, compatibilidad, precio, stock, imagen)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (codigo, nombre, marca, compatibilidad, precio, stock, image_url))
    else:
        cursor.execute("""
            INSERT INTO productos (codigo, nombre, marca, compatibilidad, precio, stock, imagen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, marca, compatibilidad, precio, stock, image_url))
    
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/editar", methods=["POST"])
@login_required
def editar():
    prod_id = int(request.form["producto_id"])
    nuevo_precio = float(request.form["precio"])
    nuevo_stock = int(request.form["stock"])

    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("UPDATE productos SET precio = %s, stock = %s WHERE id = %s", (nuevo_precio, nuevo_stock, prod_id))
    else:
        cursor.execute("UPDATE productos SET precio = ?, stock = ? WHERE id = ?", (nuevo_precio, nuevo_stock, prod_id))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar(id):
    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
    else:
        cursor.execute("DELETE FROM productos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/vender", methods=["POST"])
@login_required
def vender():
    prod_id = int(request.form["producto_id"])
    cant = int(request.form["cantidad"])

    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("SELECT nombre, precio, stock FROM productos WHERE id = %s", (prod_id,))
    else:
        cursor.execute("SELECT nombre, precio, stock FROM productos WHERE id = ?", (prod_id,))
    
    prod = cursor.fetchone()

    if prod:
        nombre = prod[0] if isinstance(prod, tuple) else prod['nombre']
        precio = prod[1] if isinstance(prod, tuple) else prod['precio']
        stock = prod[2] if isinstance(prod, tuple) else prod['stock']

        if stock >= cant:
            nuevo_stock = stock - cant
            total = precio * cant
            
            if DATABASE_URL:
                cursor.execute("UPDATE productos SET stock = %s WHERE id = %s", (nuevo_stock, prod_id))
                cursor.execute("INSERT INTO ventas (producto_id, nombre, cantidad, total) VALUES (%s, %s, %s, %s)",
                               (prod_id, nombre, cant, total))
            else:
                cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, prod_id))
                cursor.execute("INSERT INTO ventas (producto_id, nombre, cantidad, total) VALUES (?, ?, ?, ?)",
                               (prod_id, nombre, cant, total))
            conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/ventas")
@login_required
def ver_ventas():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ventas ORDER BY fecha DESC")
    ventas = cursor.fetchall()
    conn.close()
    return render_template("ventas.html", ventas=ventas)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)