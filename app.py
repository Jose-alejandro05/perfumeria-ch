from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cambia-esta-clave-por-una-segura')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///colonias.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Carpeta donde se guardan las imágenes subidas por el admin
CARPETA_SUBIDAS = os.path.join(app.root_path, 'static', 'img', 'productos')
os.makedirs(CARPETA_SUBIDAS, exist_ok=True)
EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

db = SQLAlchemy(app)

# ---------------------------------------------------------
# CREDENCIALES DE ADMINISTRADOR
# En un proyecto real esto NO debería ir escrito en el código,
# sino en variables de entorno. Aquí lo dejamos simple para
# que puedas cambiarlas fácilmente.
# ---------------------------------------------------------
ADMIN_USUARIO = os.environ.get('ADMIN_USUARIO', 'admin')
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'colonias2026'))

# ---------------------------------------------------------
# DATOS DE LA CUENTA PARA TRANSFERENCIAS
# Cámbialos por los datos reales de tu cuenta bancaria/Nequi/Daviplata.
# ---------------------------------------------------------
CUENTA_BANCO = {
    'banco': 'Nequi',
    'numero_cuenta': ' 3006115265',
    'titular': 'Camilo Heredia',
}

# ---------------------------------------------------------
# CONFIGURACIÓN DE CORREO (para enviar confirmación al cliente)
# Se leen de variables de entorno para no dejar contraseñas en el código.
# Ver README.md para instrucciones de cómo configurarlo con Gmail.
# ---------------------------------------------------------
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')  # tu correo remitente
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # contraseña de aplicación
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

CORREO_CONFIGURADO = bool(app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD'])

try:
    from flask_mail import Mail, Message
    mail = Mail(app)
except ImportError:
    mail = None
    CORREO_CONFIGURADO = False

# ---------------------------------------------------------
# MODELOS (tablas de la base de datos)
# ---------------------------------------------------------

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    marca = db.Column(db.String(80), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    precio = db.Column(db.Float, nullable=False)
    precio_texto = db.Column(db.String(50), nullable=True)  # el precio tal como el admin lo escribió
    stock = db.Column(db.Integer, default=0)
    imagen_url = db.Column(db.String(300), default='/static/img/sin-imagen.png')
    genero = db.Column(db.String(20), default='Unisex')  # Hombre, Mujer, Unisex
    ml = db.Column(db.Integer, default=100)

    def __repr__(self):
        return f'<Producto {self.nombre}>'


class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_nombre = db.Column(db.String(120), nullable=False)
    cliente_email = db.Column(db.String(120), nullable=False)
    cliente_direccion = db.Column(db.String(300), nullable=False)
    total = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    detalle = db.Column(db.Text)  # guardamos un resumen simple del pedido
    metodo_pago = db.Column(db.String(30), default='Contraentrega')
    referencia_pago = db.Column(db.String(100), nullable=True)  # nro. de comprobante si fue transferencia


import re

def interpretar_precio(texto):
    """
    Convierte lo que el admin escribió (ej. '320.000', '320000', '$320.000')
    en un número usable para sumar el carrito, sin cambiar cómo se ve.
    """
    solo_digitos = re.sub(r'[^\d]', '', texto or '')
    return float(solo_digitos) if solo_digitos else 0.0


# ---------------------------------------------------------
# MANEJO DE IMÁGENES SUBIDAS POR EL ADMIN
# ---------------------------------------------------------

def extension_permitida(nombre_archivo):
    return '.' in nombre_archivo and \
        nombre_archivo.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS


def guardar_imagen_subida(archivo):
    """Guarda el archivo subido con un nombre único y devuelve la ruta pública, o None si no hay archivo válido."""
    if not archivo or archivo.filename == '':
        return None
    if not extension_permitida(archivo.filename):
        flash('Formato de imagen no permitido. Usa PNG, JPG, JPEG, WEBP o GIF.', 'danger')
        return None

    extension = secure_filename(archivo.filename).rsplit('.', 1)[1].lower()
    nombre_unico = f'{uuid.uuid4().hex}.{extension}'
    ruta_completa = os.path.join(CARPETA_SUBIDAS, nombre_unico)
    archivo.save(ruta_completa)
    return f'/static/img/productos/{nombre_unico}'


# ---------------------------------------------------------
# ENVÍO DE CORREO DE CONFIRMACIÓN
# ---------------------------------------------------------

def enviar_confirmacion(pedido, items):
    if not CORREO_CONFIGURADO or mail is None:
        return False, 'El correo no está configurado todavía (ver README.md).'

    lineas = '\n'.join([f"- {i['cantidad']} x {i['producto'].nombre} ({i['producto'].marca})" for i in items])
    cuerpo = f"""Hola {pedido.cliente_nombre},

¡Gracias por tu compra en PERFUMERIA CH!

Pedido #{pedido.id}
Total: ${pedido.total:,.0f}

Productos:
{lineas}

Método de pago: {pedido.metodo_pago}
Dirección de envío: {pedido.cliente_direccion}

Te contactaremos pronto para coordinar la entrega.

— PERFUMERIA CH
"""
    try:
        msg = Message(
            subject=f'Confirmación de tu pedido #{pedido.id} — PERFUMERIA CH',
            recipients=[pedido.cliente_email],
            body=cuerpo
        )
        mail.send(msg)
        return True, 'Correo enviado.'
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------
# FUNCIONES AUXILIARES DEL CARRITO
# El carrito se guarda en la sesión del navegador como:
# {"3": 2, "5": 1}  ->  {id_producto: cantidad}
# ---------------------------------------------------------

def obtener_carrito():
    return session.get('carrito', {})


def guardar_carrito(carrito):
    session['carrito'] = carrito
    session.modified = True


def calcular_total(carrito):
    total = 0
    items = []
    for id_producto, cantidad in carrito.items():
        producto = Producto.query.get(int(id_producto))
        if producto:
            subtotal = producto.precio * cantidad
            total += subtotal
            items.append({
                'producto': producto,
                'cantidad': cantidad,
                'subtotal': subtotal
            })
    return items, total


# ---------------------------------------------------------
# RUTAS PÚBLICAS (catálogo)
# ---------------------------------------------------------

@app.route('/')
def index():
    genero = request.args.get('genero')
    busqueda = request.args.get('q')

    query = Producto.query

    if genero and genero != 'Todos':
        query = query.filter_by(genero=genero)

    if busqueda:
        query = query.filter(
            Producto.nombre.ilike(f'%{busqueda}%') |
            Producto.marca.ilike(f'%{busqueda}%')
        )

    productos = query.order_by(Producto.nombre).all()
    return render_template('index.html', productos=productos, genero=genero, busqueda=busqueda or '')


@app.route('/producto/<int:producto_id>')
def detalle(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    return render_template('detalle.html', producto=producto)


# ---------------------------------------------------------
# CARRITO DE COMPRAS
# ---------------------------------------------------------

@app.route('/agregar_carrito/<int:producto_id>', methods=['POST'])
def agregar_carrito(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    cantidad = int(request.form.get('cantidad', 1))

    carrito = obtener_carrito()
    id_str = str(producto_id)
    carrito[id_str] = carrito.get(id_str, 0) + cantidad
    guardar_carrito(carrito)

    flash(f'"{producto.nombre}" se agregó al carrito.', 'success')
    return redirect(url_for('index'))


@app.route('/carrito')
def ver_carrito():
    carrito = obtener_carrito()
    items, total = calcular_total(carrito)
    return render_template('carrito.html', items=items, total=total)


@app.route('/actualizar_carrito/<int:producto_id>', methods=['POST'])
def actualizar_carrito(producto_id):
    carrito = obtener_carrito()
    nueva_cantidad = int(request.form.get('cantidad', 0))
    id_str = str(producto_id)

    if nueva_cantidad <= 0:
        carrito.pop(id_str, None)
    else:
        carrito[id_str] = nueva_cantidad

    guardar_carrito(carrito)
    return redirect(url_for('ver_carrito'))


@app.route('/eliminar_carrito/<int:producto_id>')
def eliminar_carrito(producto_id):
    carrito = obtener_carrito()
    carrito.pop(str(producto_id), None)
    guardar_carrito(carrito)
    return redirect(url_for('ver_carrito'))


# ---------------------------------------------------------
# CHECKOUT (finalizar compra)
# ---------------------------------------------------------

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    carrito = obtener_carrito()
    items, total = calcular_total(carrito)

    if not items:
        flash('Tu carrito está vacío.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        direccion = request.form.get('direccion')
        metodo_pago = request.form.get('metodo_pago', 'Contraentrega')
        referencia_pago = request.form.get('referencia_pago', '').strip() or None

        resumen = ', '.join([f"{i['cantidad']}x {i['producto'].nombre}" for i in items])

        pedido = Pedido(
            cliente_nombre=nombre,
            cliente_email=email,
            cliente_direccion=direccion,
            total=total,
            detalle=resumen,
            metodo_pago=metodo_pago,
            referencia_pago=referencia_pago
        )

        # Descontamos stock
        for i in items:
            i['producto'].stock = max(0, i['producto'].stock - i['cantidad'])

        db.session.add(pedido)
        db.session.commit()

        correo_enviado, _ = enviar_confirmacion(pedido, items)

        session['carrito'] = {}  # vaciamos el carrito
        return render_template('checkout.html', exito=True, pedido=pedido, correo_enviado=correo_enviado)

    return render_template('checkout.html', exito=False, items=items, total=total, cuenta=CUENTA_BANCO)


# ---------------------------------------------------------
# LOGIN DE ADMINISTRADOR
# ---------------------------------------------------------

def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if not session.get('es_admin'):
            flash('Debes iniciar sesión para acceder a esa página.', 'warning')
            return redirect(url_for('login', siguiente=request.path))
        return f(*args, **kwargs)
    return decorador


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')

        if usuario == ADMIN_USUARIO and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['es_admin'] = True
            flash('Sesión iniciada correctamente.', 'success')
            siguiente = request.form.get('siguiente') or url_for('admin')
            return redirect(siguiente)
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    siguiente = request.args.get('siguiente', '')
    return render_template('login.html', siguiente=siguiente)


@app.route('/logout')
def logout():
    session.pop('es_admin', None)
    flash('Sesión cerrada.', 'success')
    return redirect(url_for('index'))


@app.route('/admin/pedidos')
@login_requerido
def pedidos():
    lista_pedidos = Pedido.query.order_by(Pedido.fecha.desc()).all()
    return render_template('pedidos.html', pedidos=lista_pedidos)


# ---------------------------------------------------------
# ADMINISTRACIÓN (agregar / editar / borrar productos)
# Protegido con login: solo entra quien inicie sesión.
# ---------------------------------------------------------

@app.route('/admin', methods=['GET', 'POST'])
@login_requerido
def admin():
    if request.method == 'POST':
        ruta_imagen = guardar_imagen_subida(request.files.get('imagen'))
        precio_texto = request.form.get('precio', '').strip()

        producto = Producto(
            nombre=request.form.get('nombre'),
            marca=request.form.get('marca'),
            descripcion=request.form.get('descripcion'),
            precio=interpretar_precio(precio_texto),
            precio_texto=precio_texto,
            stock=int(request.form.get('stock')),
            imagen_url=ruta_imagen or '/static/img/sin-imagen.png',
            genero=request.form.get('genero'),
            ml=int(request.form.get('ml') or 100)
        )
        db.session.add(producto)
        db.session.commit()
        flash('Producto agregado correctamente.', 'success')
        return redirect(url_for('admin'))

    productos = Producto.query.order_by(Producto.id.desc()).all()
    return render_template('admin.html', productos=productos)


@app.route('/admin/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_requerido
def editar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)

    if request.method == 'POST':
        precio_texto = request.form.get('precio', '').strip()

        producto.nombre = request.form.get('nombre')
        producto.marca = request.form.get('marca')
        producto.descripcion = request.form.get('descripcion')
        producto.precio = interpretar_precio(precio_texto)
        producto.precio_texto = precio_texto
        producto.stock = int(request.form.get('stock'))
        producto.genero = request.form.get('genero')
        producto.ml = int(request.form.get('ml') or 100)

        nueva_imagen = guardar_imagen_subida(request.files.get('imagen'))
        if nueva_imagen:
            producto.imagen_url = nueva_imagen

        db.session.commit()
        flash('Producto actualizado correctamente.', 'success')
        return redirect(url_for('admin'))

    return render_template('editar.html', p=producto)


@app.route('/admin/borrar/<int:producto_id>')
@login_requerido
def borrar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado.', 'success')
    return redirect(url_for('admin'))


# ---------------------------------------------------------
# INICIALIZACIÓN: crea la base de datos y datos de ejemplo
# ---------------------------------------------------------

def inicializar_datos():
    db.create_all()
    if Producto.query.count() == 0:
        ejemplos = [
            Producto(nombre='Sauvage', marca='Dior', descripcion='Fragancia fresca y especiada.',
                      precio=320000, stock=15, genero='Hombre', ml=100,
                      imagen_url='/static/img/sin-imagen.png'),
            Producto(nombre='Good Girl', marca='Carolina Herrera', descripcion='Floral y seductora.',
                      precio=350000, stock=10, genero='Mujer', ml=80,
                      imagen_url='/static/img/sin-imagen.png'),
            Producto(nombre='CK One', marca='Calvin Klein', descripcion='Cítrica y ligera, para todos.',
                      precio=180000, stock=20, genero='Unisex', ml=100,
                      imagen_url='/static/img/sin-imagen.png'),
        ]
        db.session.bulk_save_objects(ejemplos)
        db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        inicializar_datos()
    puerto = int(os.environ.get('PORT', 5000))
    modo_debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=puerto, debug=modo_debug)
else:
    # Cuando un servidor WSGI (gunicorn) importa la app, también inicializamos la BD
    with app.app_context():
        inicializar_datos()
