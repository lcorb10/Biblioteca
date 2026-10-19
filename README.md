# Biblioteca Universitaria · Laboratorio 01

Aplicación web en **Python + Flask** con **MySQL 8** para gestionar el préstamo y la devolución de libros.

## Estructura

```
app.py              Rutas Flask (una URL por pantalla) y permisos
db.py               Conexión MySQL, consultas SQL y reglas de negocio (transacciones)
templates/          Plantillas HTML (Jinja2)
static/css/app.css  Sistema visual "Estante" y animaciones
static/js/app.js    Interacciones (multa en vivo, confirmaciones, tokens, tooltips)
schema.sql          Script de creación de tablas e inserts básicos
modelo.md           Modelo entidad-relación (Mermaid) y modelo relacional
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
| Bibliotecario | usuario `admin` · clave `admin123` |
| Lector (estudiante) | código `U001` · identificación `1001001001` |

## Funcionalidades frente al enunciado

| Requisito | Dónde |
|---|---|
| CRUD de libros (varios autores y categorías) | Libros |
| CRUD de ejemplares (disponible / prestado / perdido) | Ejemplares |
| CRUD de usuarios (estudiante/docente, activo/bloqueado) | Usuarios |
| Búsqueda por título, autor, ISBN, categoría y disponibilidad | Catálogo |
| El usuario busca y solicita; el bibliotecario aprueba | Catálogo → Préstamos |
| Validar usuario activo y ejemplar disponible | `db._validar_y_prestar` (con `SELECT … FOR UPDATE`) |
| Devolución, multa automática por día y observaciones | Devolver |
| Historial por usuario | Usuarios → Historial / Mis libros |
| Activos y vencidos, más prestados por periodo, usuarios top, inventario | Reportes |
| Tarifa de multa configurable | tabla `configuracion` (`tarifa_multa_dia`) |
