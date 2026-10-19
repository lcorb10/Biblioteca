# Biblioteca Universitaria · Laboratorio 01

Aplicación web en **Python + Flask** con **MySQL 8** (driver **PyMySQL**) para gestionar el préstamo y la devolución de libros de la biblioteca de la universidad.

## Entregables del laboratorio

| Documento pedido | Archivo |
|---|---|
| Diagrama entidad-relación (MER) | [`docs/MER.png`](docs/MER.png) · fuente [`docs/mer.mmd`](docs/mer.mmd) |
| Diagrama relacional | [`docs/Modelo_Relacional.png`](docs/Modelo_Relacional.png) · fuente [`docs/relacional.mmd`](docs/relacional.mmd) |
| Script de creación de tablas e inserts básicos | [`schema.sql`](schema.sql) |
| Archivos para ejecutar la aplicación | `app.py`, `db.py`, `templates/`, `static/`, `requirements.txt` |

## Estructura

```
app.py              Rutas Flask (una URL por pantalla), permisos y exportación CSV
db.py               Conexión MySQL, consultas SQL y reglas de negocio (transacciones)
templates/          Plantillas HTML (Jinja2)
static/css/app.css  Sistema visual "Estante", modo oscuro y animaciones
static/js/app.js    Interacciones (multa en vivo, Ctrl+K, panel SQL, tema, filtros)
schema.sql          Creación de tablas, restricciones y datos de ejemplo
docs/               Diagramas MER y relacional
config.example.toml Plantilla de credenciales (copiar como config.toml, que no se sube)
legacy_streamlit/   Versión anterior en Streamlit (solo referencia)
```

## Cómo ejecutar

1. Cargar la base de datos: abrir `schema.sql` en MySQL Workbench y ejecutarlo completo.
2. Copiar `config.example.toml` como `config.toml` y poner los datos de MySQL (host, usuario, clave y base `biblioteca`).
3. En una terminal, dentro de esta carpeta:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

4. Abrir http://127.0.0.1:5000

| Rol | Ingreso |
|---|---|
| Bibliotecario (administrador) | usuario `admin` · clave `admin123` |
| Lector (estudiante) | código `U001` · identificación `1001001001` |
| Lector nuevo | botón **Crea tu cuenta de lector** en la pantalla de ingreso |

## Cumplimiento del enunciado

| Requisito | Dónde |
|---|---|
| Libros: ISBN, título, autor(es), editorial, año, categorías, descripción | Libros (CRUD) · tablas `libro`, `libro_autor`, `libro_categoria` |
| Ejemplares: código de barras, ubicación, estado (disponible / prestado / perdido) | Ejemplares (CRUD) · tabla `ejemplar` |
| Búsqueda por título, autor, ISBN, categoría y disponibilidad | Catálogo y buscador rápido (Ctrl+K) |
| Usuarios: código, identificación, nombres, correo, rol, carrera, estado | Usuarios (CRUD) y registro de lectores |
| Historial de préstamos por usuario | Usuarios → Historial · Mis libros |
| Préstamo: usuario + ejemplar + fecha de préstamo + vencimiento | Préstamos (aprobación y préstamo directo) |
| Validar usuario activo y ejemplar disponible | `db._validar_y_prestar` (transacción con `SELECT … FOR UPDATE`) |
| Devolución: ejemplar vuelve a disponible, multa automática, observaciones | Devolver · `db.registrar_devolucion` |
| Tarifa de multa por día | tabla `configuracion` (`tarifa_multa_dia`) |
| Préstamos activos y vencidos | Reportes |
| Libros más prestados por periodo | Reportes (filtro de fechas) |
| Usuarios con más préstamos | Reportes (filtro de fechas) |
| Inventario por estado | Reportes e Inicio (estante) |
| Un libro con varios ejemplares y varios autores | Relaciones 1:N `libro`–`ejemplar` y N:M `libro`–`autor` |
| Un usuario puede tener varios préstamos | Relación 1:N `usuario`–`prestamo` (máximo configurable) |
| Administrador/bibliotecario aprueba el préstamo y la devolución | Tabla `personal`; `prestamo.id_personal` y `devolucion.id_personal` |
| El usuario busca el libro y solicita el préstamo | Catálogo → Solicitar préstamo → queda en estado `solicitado` |

## Extras de la interfaz

- **Ver SQL**: botón flotante que muestra las sentencias reales enviadas a MySQL en cada pantalla (incluida la transacción de la última acción).
- Portadas reales por ISBN (Open Library) con portada generada como respaldo.
- Página de detalle de cada libro con ejemplares e historial.
- Comprobante imprimible de préstamo y devolución.
- Reportes con tendencia mensual, mapa de calor diario y exportación a CSV.
- Modo claro / oscuro, diseño adaptado a celular y animación de bienvenida.

## Despliegue

En la nube la configuración se lee de variables de entorno en lugar de `config.toml`:
`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_SSL=1` (si el proveedor lo exige) y `SECRET_KEY`.
