# PERFUMERIA CH — Tienda de Colonias en Flask

## ¿Qué incluye?
- Catálogo de productos con filtro por género y buscador
- Página de detalle por producto
- Carrito de compras (guardado en la sesión del navegador)
- Checkout con formulario de datos del cliente y descuento de stock
- Panel de administración para agregar/borrar productos
- Base de datos SQLite (se crea automáticamente, no requiere instalación extra)

## Requisitos
- Python 3.9 o superior

## Instalación (paso a paso)

1. Abre una terminal dentro de la carpeta `tienda_colonias`.

2. Crea un entorno virtual (recomendado):
   ```bash
   python -m venv venv
   ```
   Actívalo:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Ejecuta la aplicación:
   ```bash
   python app.py
   ```

5. Abre tu navegador en:
   ```
   http://127.0.0.1:5000
   ```

La primera vez que se ejecuta, se crea automáticamente el archivo `colonias.db`
con 3 colonias de ejemplo (Sauvage, Good Girl, CK One).

## Cómo agregar tus propias colonias
Ve a `http://127.0.0.1:5000/login` e inicia sesión (usuario: `admin`, contraseña: `colonias2026`),
luego entra a `/admin` y usa el formulario para agregar productos con nombre, marca, precio, stock,
mililitros y una **imagen desde tu computador** (botón "Elegir archivo" — acepta PNG, JPG, JPEG, WEBP o GIF).
Las imágenes subidas se guardan automáticamente en `static/img/productos/`.

## Pagos por transferencia
En `/checkout`, el cliente puede elegir "Transferencia bancaria" o "Pago contraentrega".
Los datos de tu cuenta (banco, número, titular) están en `app.py`, en el diccionario `CUENTA_BANCO`.
Cámbialos por los datos reales de tu cuenta antes de publicar la tienda:

```python
CUENTA_BANCO = {
    'banco': 'Bancolombia',
    'tipo_cuenta': 'Ahorros',
    'numero_cuenta': '000-000000-00',
    'titular': 'PERFUMERIA CH',
    'documento': 'C.C. 000000000',
}
```

## Historial de pedidos
Todos los pedidos (cliente, dirección, productos, total y método de pago) quedan guardados
en la base de datos. Como administrador, entra a **Pedidos** en el menú para verlos todos.

## Enviar confirmación por correo al cliente
Por defecto el correo automático está desactivado (no tenemos cómo conocer tus credenciales
de correo). Para activarlo:

1. Si usas Gmail, crea una "contraseña de aplicación" en tu cuenta de Google
   (Cuenta de Google → Seguridad → Verificación en dos pasos → Contraseñas de aplicaciones).
2. Antes de ejecutar `python app.py`, define estas variables de entorno con tus datos:

   **Windows (PowerShell):**
   ```powershell
   $env:MAIL_USERNAME="tu_correo@gmail.com"
   $env:MAIL_PASSWORD="tu_contraseña_de_aplicacion"
   python app.py
   ```

   **Mac/Linux:**
   ```bash
   export MAIL_USERNAME="tu_correo@gmail.com"
   export MAIL_PASSWORD="tu_contraseña_de_aplicacion"
   python app.py
   ```

3. Listo — cuando un cliente complete una compra, recibirá un correo de confirmación
   automáticamente. Si no configuras estas variables, la tienda sigue funcionando igual,
   solo que no se envía el correo (y el pedido se guarda igual en el historial).

## Próximos pasos sugeridos (para hacerla más real)
- Agregar login de administrador (Flask-Login) para proteger `/admin`
- Integrar una pasarela de pagos real (Wompi, PayU, Stripe)
- Subida de imágenes desde el propio formulario en vez de URL
- Desplegarla en un servidor (Render, PythonAnywhere, Railway) para que sea pública
