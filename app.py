"""Biblioteca Universitaria — aplicación Flask (Laboratorio 01, Bases de Datos)."""
import csv
import io
import os
import zlib
from datetime import date, datetime, timedelta
from functools import wraps

import pymysql
from flask import (Flask, Response, abort, flash, g, has_request_context, redirect, render_template, request,
                   session, url_for)

import db

app = Flask(__name__)
app.secret_key = db.CONFIG.get("flask", {}).get("secret_key") or os.urandom(24)


# ======================================================
# Panel "Ver SQL": guarda las sentencias que ejecuta cada petición
# ======================================================
def _guardar_sql(texto):
    if has_request_context() and "sql" in g and not g.get("sql_mute"):
        g.sql.append(texto)


db.on_sql(_guardar_sql)


# Una conexión MySQL por petición (se abre al primer uso y se cierra al terminar)
def _conexion_peticion():
    if not has_request_context():
        return None
    if "db_conn" not in g:
        g.db_conn = db.get_conn(autocommit=True)
    return g.db_conn


db.usar_conexion_compartida(_conexion_peticion)


@app.teardown_appcontext
def _cerrar_conexion(exc):
    conn = g.pop("db_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


@app.before_request
def _sql_inicio():
    g.sql = []


@app.after_request
def _sql_accion(resp):
    # Las acciones (POST) redirigen: se guardan para mostrarlas en la página siguiente
    if request.method == "POST" and g.get("sql"):
        sentencias, total = [], 0
        for s in g.sql:
            s = s if len(s) <= 700 else s[:700] + " …"
            total += len(s)
            if total > 2600:
                sentencias.append("-- … (más sentencias omitidas)")
                break
            sentencias.append(s)
        session["sql_prev"] = {"ruta": request.path, "sql": sentencias}
    return resp


# ======================================================
# Utilidades de vista
# ======================================================
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"]
# Paleta de lomos: tonos de encuadernación, todos con contraste AA para texto blanco
LOMOS = ["#1F6F78", "#A86E12", "#3B4DA8", "#7A4E9E", "#2E6B3F", "#9C3D2E", "#2B5C8A", "#7D5A3C"]


@app.template_filter("fecha")
def f_fecha(v, larga=False):
    if not v:
        return "—"
    if isinstance(v, str):
        return v
    return f"{v.day} {MESES[v.month - 1]} {v.year}"


@app.template_filter("hora")
def f_hora(v):
    return v.strftime("%H:%M") if isinstance(v, datetime) else ""


@app.template_filter("dinero")
def f_dinero(v):
    return "$" + f"{float(v or 0):,.0f}".replace(",", ".")


@app.template_filter("color")
def f_color(nombre):
    if not nombre:
        return "#6B625C"
    return LOMOS[zlib.crc32(("2" + nombre).encode()) % len(LOMOS)]


@app.template_filter("alto")
def f_alto(clave):
    """Alto pseudoaleatorio pero estable para cada lomo (según el ISBN)."""
    return 96 + zlib.crc32(str(clave).encode()) % 44


@app.template_filter("iniciales")
def f_iniciales(txt):
    palabras = [p for p in (txt or "").split() if p[:1].isalnum() and len(p) > 2] or (txt or "?").split()
    return "".join(p[0] for p in palabras[:2]).upper()


@app.template_filter("barras")
def f_barras(codigo):
    """Anchos de barra (decorativos) derivados del código del ejemplar."""
    h = zlib.crc32(str(codigo).encode())
    return [1 + (h >> (i % 30) ^ i * 7) % 3 for i in range(46)]


@app.template_filter("hace")
def f_hace(v):
    if not isinstance(v, datetime):
        return ""
    s = (datetime.now() - v).total_seconds()
    if s < 3600:
        return f"hace {max(int(s // 60), 1)} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    d = int(s // 86400)
    return "ayer" if d == 1 else f"hace {d} días"


def hoy_largo():
    h = date.today()
    return f"{DIAS[h.weekday()].capitalize()} {h.day} de {MESES_LARGOS[h.month - 1]}"


def parse_fecha(txt, default=None):
    try:
        return date.fromisoformat(txt)
    except (TypeError, ValueError):
        return default


def campo(nombre):
    return (request.form.get(nombre) or "").strip()


def lista(nombre):
    return [x.strip() for x in (request.form.get(nombre) or "").split(",") if x.strip()]


# ======================================================
# Sesión y permisos
# ======================================================
def auth():
    return session.get("auth")


def requiere(tipo=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not auth():
                return redirect(url_for("login", next=request.path))
            if tipo and auth()["tipo"] != tipo:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


NAV_PERSONAL = [
    ("inicio", "Inicio", "layout-dashboard"),
    ("catalogo", "Catálogo", "search"),
    ("libros", "Libros", "book"),
    ("ejemplares", "Ejemplares", "barcode"),
    ("usuarios", "Usuarios", "users"),
    ("prestamos", "Préstamos", "hand-helping"),
    ("devoluciones", "Devolver", "undo-2"),
    ("reportes", "Reportes", "chart-column"),
]
NAV_USUARIO = [
    ("catalogo", "Catálogo", "search"),
    ("mis_prestamos", "Mis libros", "book-marked"),
]


SECCION = {
    "libro_nuevo": "libros", "libro_editar": "libros",
    "ejemplar_nuevo": "ejemplares", "ejemplar_editar": "ejemplares",
    "usuario_nuevo": "usuarios", "usuario_editar": "usuarios", "usuario_historial": "usuarios",
    "prestamo_nuevo": "prestamos", "prestamo_comprobante": "prestamos", "libro_detalle": "catalogo",
}


@app.context_processor
def contexto():
    a = auth()
    ctx = {"auth": a, "hoy": date.today(), "hoy_largo": hoy_largo(), "pendientes": 0,
           "seccion": SECCION.get(request.endpoint, request.endpoint)}
    ctx["sql_prev"] = session.pop("sql_prev", None) if request.method == "GET" else None
    g.sql_mute = True  # las consultas de menú y buscador no son parte de la página
    if a:
        ctx["nav"] = NAV_PERSONAL if a["tipo"] == "personal" else NAV_USUARIO
        try:  # datos para el buscador rápido (Ctrl+K)
            ctx["pal_libros"] = [{"t": l["titulo"], "a": l["autores"] or "", "i": l["isbn"], "d": int(l["disponibles"]),
                                  "n": int(l["total_ejemplares"]), "c": f_color((l["categorias"] or "").split(", ")[0])}
                                 for l in db.buscar_libros()[:300]]
        except pymysql.MySQLError:
            ctx["pal_libros"] = []
        if a["tipo"] == "personal":
            try:
                ctx["pendientes"] = db.one("SELECT COUNT(*) AS n FROM prestamo WHERE estado='solicitado'")["n"]
            except pymysql.MySQLError:
                pass
    g.sql_mute = False
    return ctx


@app.errorhandler(pymysql.err.OperationalError)
def error_conexion(e):
    return render_template("error.html", titulo="Sin conexión con la base de datos",
                           detalle=f"Revisa la configuración de MySQL (config.toml o variables de entorno MYSQL_*) y que el servidor esté encendido. ({e})"), 503


@app.errorhandler(403)
def prohibido(e):
    return render_template("error.html", titulo="No tienes permiso para ver esta página",
                           detalle="Esta sección es solo para el personal de la biblioteca."), 403


@app.errorhandler(404)
def no_encontrado(e):
    return render_template("error.html", titulo="No encontramos esa página",
                           detalle="Puede que el registro se haya eliminado."), 404


# ======================================================
# Login
# ======================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    modo = request.form.get("modo") or request.args.get("modo") or "usuario"
    if request.method == "POST":
        try:
            if modo == "personal":
                a = db.autenticar_personal(campo("login"), request.form.get("clave", ""))
            else:
                a = db.autenticar_usuario(campo("codigo"), campo("identificacion"))
            if a:
                session.clear()
                session["auth"] = a
                destino = request.args.get("next") or url_for("inicio")
                return redirect(destino if destino.startswith("/") else url_for("inicio"))
            flash("Los datos no coinciden. Revisa e inténtalo de nuevo.", "error")
        except pymysql.MySQLError as e:
            flash(f"No se pudo conectar a la base de datos: {e}", "error")
    try:
        libros = db.estante(60)
    except pymysql.MySQLError:
        libros = []
    if libros and len(libros) < 22:  # con pocos ejemplares, se repiten para llenar la repisa
        libros = (libros * (22 // len(libros) + 1))[:22]
    return render_template("login.html", modo=modo, libros=libros)


@app.route("/registro", methods=["GET", "POST"])
def registro():
    """Registro de lectores (estudiantes y docentes) desde la pantalla de inicio de sesión."""
    if auth():
        return redirect(url_for("inicio"))
    u = {"rol": "estudiante"}
    if request.method == "POST":
        u = form_usuario()
        u["estado"] = "activo"
        if usuario_valido(u):
            try:
                db.crear_usuario(u)
                session.clear()
                session["auth"] = db.autenticar_usuario(u["codigo"], u["identificacion"])
                flash(f"¡Bienvenido a la biblioteca, {u['nombres'].split()[0]}! Ya puedes solicitar libros.", "ok")
                return redirect(url_for("catalogo"))
            except pymysql.MySQLError as e:
                flash(db.mensaje_error(e), "error")
    return render_template("registro.html", u=u)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ======================================================
# Inicio
# ======================================================
@app.route("/")
@requiere()
def inicio():
    if auth()["tipo"] == "usuario":
        return redirect(url_for("catalogo"))
    activos = db.prestamos_activos()
    return render_template("inicio.html", r=db.resumen(), libros=db.estante(),
                           vencidos=[p for p in activos if p["dias_retraso"] > 0][:5],
                           solicitudes=db.solicitudes_pendientes()[:4])


# ======================================================
# Catálogo (todos)
# ======================================================
@app.route("/catalogo")
@requiere()
def catalogo():
    f = {k: (request.args.get(k) or "").strip() for k in ("titulo", "autor", "isbn", "categoria")}
    f["disp"] = request.args.get("disp") == "1"
    libros = db.buscar_libros(f["titulo"], f["autor"], f["isbn"], f["categoria"], f["disp"])
    return render_template("catalogo.html", libros=libros, f=f, categorias=db.nombres("categoria"))


@app.route("/libros/<isbn>")
@requiere()
def libro_detalle(isbn):
    libro = db.get_libro(isbn) or abort(404)
    historial = db.prestamos_de_libro(isbn) if auth()["tipo"] == "personal" else []
    return render_template("libro_detalle.html", l=libro, ejemplares=db.ejemplares_de_libro(isbn),
                           historial=historial)


@app.post("/catalogo/solicitar")
@requiere("usuario")
def solicitar():
    isbn = request.form.get("isbn", "")
    try:
        db.solicitar_prestamo(auth()["id"], isbn)
        flash("Solicitud enviada. Te avisaremos cuando un bibliotecario la apruebe.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    except pymysql.MySQLError as e:
        flash(db.mensaje_error(e), "error")
    return redirect(request.referrer or url_for("catalogo"))


@app.route("/mis-prestamos")
@requiere("usuario")
def mis_prestamos():
    return render_template("mis_prestamos.html", historial=db.historial_usuario(auth()["id"]),
                           tarifa=db.tarifa_dia())


# ======================================================
# CRUD Libros
# ======================================================
@app.route("/libros")
@requiere("personal")
def libros():
    q = (request.args.get("q") or "").strip()
    return render_template("libros.html", libros=db.buscar_libros(titulo=q) if q else db.buscar_libros(), q=q)


def form_libro():
    anio = campo("anio")
    return {
        "isbn": campo("isbn"), "titulo": campo("titulo"), "editorial": campo("editorial"),
        "anio": int(anio) if anio.isdigit() else None, "descripcion": campo("descripcion"),
        "autores": lista("autores"), "categorias": lista("categorias"),
    }


def render_libro_form(libro, nuevo):
    return render_template("libro_form.html", libro=libro, nuevo=nuevo, editoriales=db.nombres("editorial"),
                           autores=db.nombres("autor"), categorias=db.nombres("categoria"))


@app.route("/libros/nuevo", methods=["GET", "POST"])
@requiere("personal")
def libro_nuevo():
    if request.method == "POST":
        d = form_libro()
        if not d["isbn"] or not d["titulo"] or not d["autores"]:
            flash("ISBN, título y al menos un autor son obligatorios.", "error")
        else:
            try:
                db.guardar_libro(d, True)
                flash(f"«{d['titulo']}» se agregó al catálogo.", "ok")
                return redirect(url_for("libros"))
            except pymysql.MySQLError as e:
                flash(db.mensaje_error(e), "error")
        d["autores"], d["categorias"] = ", ".join(d["autores"]), ", ".join(d["categorias"])
        return render_libro_form(d, True)
    return render_libro_form({}, True)


@app.route("/libros/<isbn>/editar", methods=["GET", "POST"])
@requiere("personal")
def libro_editar(isbn):
    libro = db.get_libro(isbn) or abort(404)
    if request.method == "POST":
        d = form_libro()
        d["isbn"] = isbn
        if not d["titulo"] or not d["autores"]:
            flash("Título y al menos un autor son obligatorios.", "error")
        else:
            try:
                db.guardar_libro(d, False)
                flash("Cambios guardados.", "ok")
                return redirect(url_for("libros"))
            except pymysql.MySQLError as e:
                flash(db.mensaje_error(e), "error")
        d["autores"], d["categorias"] = ", ".join(d["autores"]), ", ".join(d["categorias"])
        libro = {**libro, **d}
    ejs = db.query("SELECT * FROM ejemplar WHERE isbn=%s ORDER BY codigo_barras", (isbn,))
    return render_template("libro_form.html", libro=libro, nuevo=False, ejemplares=ejs,
                           editoriales=db.nombres("editorial"), autores=db.nombres("autor"),
                           categorias=db.nombres("categoria"))


@app.post("/libros/<isbn>/eliminar")
@requiere("personal")
def libro_eliminar(isbn):
    try:
        db.eliminar_libro(isbn)
        flash("Libro eliminado.", "ok")
    except pymysql.MySQLError as e:
        flash(db.mensaje_error(e), "error")
    return redirect(url_for("libros"))


# ======================================================
# CRUD Ejemplares
# ======================================================
@app.route("/ejemplares")
@requiere("personal")
def ejemplares():
    estado = request.args.get("estado", "")
    q = (request.args.get("q") or "").strip()
    return render_template("ejemplares.html", ejemplares=db.listar_ejemplares(estado, q), estado=estado, q=q,
                           inv=db.inventario_por_estado())


def render_ej_form(ej, nuevo):
    return render_template("ejemplar_form.html", ej=ej, nuevo=nuevo, libros=db.libros_simple(), estados=db.EST_EJ)


@app.route("/ejemplares/nuevo", methods=["GET", "POST"])
@requiere("personal")
def ejemplar_nuevo():
    if request.method == "POST":
        d = {"codigo_barras": campo("codigo_barras"), "isbn": campo("isbn"),
             "ubicacion": campo("ubicacion"), "estado": campo("estado")}
        if not d["codigo_barras"] or not d["ubicacion"] or not d["isbn"]:
            flash("Código, libro y ubicación son obligatorios.", "error")
        else:
            try:
                db.crear_ejemplar(d["codigo_barras"], d["isbn"], d["ubicacion"], d["estado"])
                flash(f"Ejemplar {d['codigo_barras']} creado.", "ok")
                return redirect(url_for("ejemplares"))
            except pymysql.MySQLError as e:
                flash(db.mensaje_error(e), "error")
        return render_ej_form(d, True)
    return render_ej_form({"isbn": request.args.get("isbn", ""), "estado": "disponible"}, True)


@app.route("/ejemplares/<int:id_ejemplar>/editar", methods=["GET", "POST"])
@requiere("personal")
def ejemplar_editar(id_ejemplar):
    ej = db.get_ejemplar(id_ejemplar) or abort(404)
    if request.method == "POST":
        d = {"codigo_barras": campo("codigo_barras"), "isbn": campo("isbn"),
             "ubicacion": campo("ubicacion"), "estado": campo("estado")}
        try:
            db.actualizar_ejemplar(id_ejemplar, d["codigo_barras"], d["isbn"], d["ubicacion"], d["estado"])
            flash("Ejemplar actualizado.", "ok")
            return redirect(url_for("ejemplares"))
        except pymysql.MySQLError as e:
            flash(db.mensaje_error(e), "error")
        ej = {**ej, **d}
    return render_ej_form(ej, False)


@app.post("/ejemplares/<int:id_ejemplar>/eliminar")
@requiere("personal")
def ejemplar_eliminar(id_ejemplar):
    try:
        db.eliminar_ejemplar(id_ejemplar)
        flash("Ejemplar eliminado.", "ok")
    except pymysql.MySQLError as e:
        flash(db.mensaje_error(e), "error")
    return redirect(url_for("ejemplares"))


# ======================================================
# CRUD Usuarios + historial
# ======================================================
@app.route("/usuarios")
@requiere("personal")
def usuarios():
    f = {k: (request.args.get(k) or "").strip() for k in ("q", "rol", "estado")}
    return render_template("usuarios.html", usuarios=db.listar_usuarios(f["q"], f["rol"], f["estado"]), f=f)


def form_usuario():
    return {"codigo": campo("codigo"), "identificacion": campo("identificacion"), "nombres": campo("nombres"),
            "correo": campo("correo"), "rol": campo("rol") or "estudiante", "carrera": campo("carrera") or None,
            "estado": campo("estado") or "activo"}


def usuario_valido(d):
    if not (d["codigo"] and d["identificacion"] and d["nombres"] and d["correo"]):
        flash("Código, identificación, nombres y correo son obligatorios.", "error")
        return False
    if "@" not in d["correo"]:
        flash("El correo no parece válido.", "error")
        return False
    return True


@app.route("/usuarios/nuevo", methods=["GET", "POST"])
@requiere("personal")
def usuario_nuevo():
    u = {"rol": "estudiante", "estado": "activo"}
    if request.method == "POST":
        u = form_usuario()
        if usuario_valido(u):
            try:
                db.crear_usuario(u)
                flash(f"{u['nombres']} quedó registrado.", "ok")
                return redirect(url_for("usuarios"))
            except pymysql.MySQLError as e:
                flash(db.mensaje_error(e), "error")
    return render_template("usuario_form.html", u=u, nuevo=True)


@app.route("/usuarios/<int:id_usuario>/editar", methods=["GET", "POST"])
@requiere("personal")
def usuario_editar(id_usuario):
    u = db.get_usuario(id_usuario) or abort(404)
    if request.method == "POST":
        d = form_usuario()
        if usuario_valido(d):
            try:
                db.actualizar_usuario(id_usuario, d)
                flash("Usuario actualizado.", "ok")
                return redirect(url_for("usuarios"))
            except pymysql.MySQLError as e:
                flash(db.mensaje_error(e), "error")
        u = {**u, **d}
    return render_template("usuario_form.html", u=u, nuevo=False)


@app.post("/usuarios/<int:id_usuario>/eliminar")
@requiere("personal")
def usuario_eliminar(id_usuario):
    try:
        db.eliminar_usuario(id_usuario)
        flash("Usuario eliminado.", "ok")
    except pymysql.MySQLError as e:
        flash(db.mensaje_error(e), "error")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/<int:id_usuario>/historial")
@requiere("personal")
def usuario_historial(id_usuario):
    u = db.get_usuario(id_usuario) or abort(404)
    return render_template("historial.html", u=u, historial=db.historial_usuario(id_usuario))


# ======================================================
# Préstamos
# ======================================================
@app.route("/prestamos")
@requiere("personal")
def prestamos():
    filtro = request.args.get("filtro", "todos")
    activos = db.prestamos_activos()
    conteo = {"todos": len(activos), "vencidos": sum(1 for p in activos if p["dias_retraso"] > 0)}
    conteo["vigentes"] = conteo["todos"] - conteo["vencidos"]
    if filtro == "vencidos":
        activos = [p for p in activos if p["dias_retraso"] > 0]
    elif filtro == "vigentes":
        activos = [p for p in activos if p["dias_retraso"] == 0]
    return render_template("prestamos.html", solicitudes=db.solicitudes_pendientes(), activos=activos,
                           filtro=filtro, conteo=conteo, venc_default=date.today() + timedelta(days=db.dias_prestamo()))


@app.post("/prestamos/<int:id_prestamo>/aprobar")
@requiere("personal")
def prestamo_aprobar(id_prestamo):
    try:
        venc = parse_fecha(request.form.get("vence"))
        if not venc:
            raise ValueError("Indica la fecha de vencimiento.")
        db.aprobar_solicitud(id_prestamo, int(request.form["id_ejemplar"]), auth()["id"], venc)
        flash("Préstamo aprobado. El ejemplar quedó marcado como prestado.", "ok")
    except (ValueError, KeyError) as e:
        flash(str(e) if isinstance(e, ValueError) else "Selecciona un ejemplar.", "error")
    except pymysql.MySQLError as e:
        flash(db.mensaje_error(e), "error")
    return redirect(url_for("prestamos"))


@app.post("/prestamos/<int:id_prestamo>/rechazar")
@requiere("personal")
def prestamo_rechazar(id_prestamo):
    db.rechazar_solicitud(id_prestamo, auth()["id"])
    flash("Solicitud rechazada.", "ok")
    return redirect(url_for("prestamos"))


@app.route("/prestamos/<int:id_prestamo>/comprobante")
@requiere()
def prestamo_comprobante(id_prestamo):
    p = db.get_prestamo_detalle(id_prestamo) or abort(404)
    if auth()["tipo"] == "usuario" and p["id_usuario"] != auth()["id"]:
        abort(403)
    if p["estado"] not in ("activo", "devuelto"):
        abort(404)
    return render_template("comprobante.html", p=p, tarifa=db.tarifa_dia())


@app.route("/prestamos/nuevo", methods=["GET", "POST"])
@requiere("personal")
def prestamo_nuevo():
    dias = db.dias_prestamo()
    if request.method == "POST":
        try:
            fp = parse_fecha(request.form.get("fecha_prestamo"), date.today())
            fv = parse_fecha(request.form.get("fecha_vencimiento"))
            if not fv:
                raise ValueError("Indica la fecha de vencimiento.")
            db.prestamo_directo(int(request.form["id_usuario"]), int(request.form["id_ejemplar"]),
                                auth()["id"], fp, fv)
            flash("Préstamo registrado.", "ok")
            return redirect(url_for("prestamos"))
        except (ValueError, KeyError) as e:
            flash(str(e) if isinstance(e, ValueError) else "Selecciona usuario y ejemplar.", "error")
        except pymysql.MySQLError as e:
            flash(db.mensaje_error(e), "error")
    return render_template("prestamo_nuevo.html", usuarios=db.listar_usuarios(),
                           ejemplares=db.ejemplares_disponibles(), dias=dias,
                           venc_default=date.today() + timedelta(days=dias))


# ======================================================
# Devoluciones
# ======================================================
@app.route("/devoluciones", methods=["GET", "POST"])
@requiere("personal")
def devoluciones():
    if request.method == "POST":
        try:
            f_dev = parse_fecha(request.form.get("fecha_devolucion"), date.today())
            cond = request.form.get("condicion", "bueno")
            if cond not in db.CONDICIONES:
                raise ValueError("Condición no válida.")
            retraso, multa = db.registrar_devolucion(int(request.form["id_prestamo"]), auth()["id"], f_dev,
                                                     cond, campo("observaciones"))
            if retraso:
                flash(f"Devolución registrada con {retraso} día(s) de retraso: multa de {f_dinero(multa)}.", "warn")
            else:
                flash("Devolución registrada a tiempo. El ejemplar vuelve al estante.", "ok")
            return redirect(url_for("devoluciones"))
        except (ValueError, KeyError) as e:
            flash(str(e) if isinstance(e, ValueError) else "Selecciona un préstamo.", "error")
        except pymysql.MySQLError as e:
            flash(db.mensaje_error(e), "error")
    return render_template("devoluciones.html", activos=db.prestamos_activos(), tarifa=db.tarifa_dia(),
                           sel=request.args.get("prestamo", type=int), ultimas=db.ultimas_devoluciones(),
                           condiciones=db.CONDICIONES)


# ======================================================
# Reportes
# ======================================================
@app.route("/reportes")
@requiere("personal")
def reportes():
    ini = parse_fecha(request.args.get("desde"), date.today() - timedelta(days=90))
    fin = parse_fecha(request.args.get("hasta"), date.today())
    activos = db.prestamos_activos()
    por_dia = db.prestamos_por_dia(26)
    # mapa de calor: columnas = semanas, filas = días (lunes a domingo)
    inicio_mapa = date.today() - timedelta(days=date.today().weekday() + 25 * 7)
    semanas = [[(d, por_dia.get(d, 0)) for d in (inicio_mapa + timedelta(days=w * 7 + i) for i in range(7))]
               for w in range(26)]
    return render_template("reportes.html", activos=activos, ini=ini, fin=fin,
                           vencidos=sum(1 for p in activos if p["dias_retraso"] > 0),
                           top_libros=db.libros_mas_prestados(ini, fin), top_usuarios=db.usuarios_mas_prestamos(ini, fin),
                           inv=db.inventario_por_estado(), libros=db.estante(), por_mes=db.prestamos_por_mes(12),
                           semanas=semanas, max_dia=max(por_dia.values(), default=0), meses_nombres=MESES)


@app.route("/reportes/<tipo>.csv")
@requiere("personal")
def reporte_csv(tipo):
    """Exporta un reporte a CSV (separado por punto y coma, se abre directo en Excel)."""
    ini = parse_fecha(request.args.get("desde"), date.today() - timedelta(days=90))
    fin = parse_fecha(request.args.get("hasta"), date.today())
    if tipo == "activos":
        cab = ["Préstamo", "Libro", "ISBN", "Ejemplar", "Lector", "Código", "Prestado", "Vence", "Días de retraso",
               "Multa estimada"]
        filas = [[p["id_prestamo"], p["titulo"], p["isbn"], p["codigo_barras"], p["usuario"], p["codigo"],
                  p["fecha_prestamo"], p["fecha_vencimiento"], p["dias_retraso"], float(p["multa_estimada"])]
                 for p in db.prestamos_activos()]
    elif tipo == "libros-mas-prestados":
        cab = ["Libro", "ISBN", "Préstamos"]
        filas = [[r["titulo"], r["isbn"], r["prestamos"]] for r in db.libros_mas_prestados(ini, fin, 100)]
    elif tipo == "usuarios-mas-prestamos":
        cab = ["Código", "Nombres", "Rol", "Préstamos"]
        filas = [[r["codigo"], r["nombres"], r["rol"], r["prestamos"]] for r in db.usuarios_mas_prestamos(ini, fin, 100)]
    elif tipo == "inventario":
        cab = ["Código de barras", "Libro", "ISBN", "Ubicación", "Estado"]
        filas = [[e["codigo_barras"], e["titulo"], e["isbn"], e["ubicacion"], e["estado"]] for e in db.listar_ejemplares()]
    else:
        abort(404)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(cab)
    w.writerows(filas)
    nombre = f"{tipo}_{date.today().isoformat()}.csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})


if __name__ == "__main__":
    app.run(debug=True)
