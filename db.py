"""Acceso a datos: conexión MySQL, consultas y reglas de negocio de la biblioteca."""
import hashlib
import hmac
import os
import tomllib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pymysql

BASE_DIR = Path(__file__).resolve().parent


def load_config():
    """Lee variables de entorno (para el despliegue en la nube) o config.toml (en local)."""
    if os.environ.get("MYSQL_HOST", "").strip():
        return {
            "mysql": {"host": os.environ["MYSQL_HOST"].strip(), "port": os.environ.get("MYSQL_PORT", "").strip() or 3306,
                      "user": os.environ.get("MYSQL_USER", "").strip(), "password": os.environ.get("MYSQL_PASSWORD", ""),
                      "database": os.environ.get("MYSQL_DATABASE", "biblioteca"),
                      "ssl": os.environ.get("MYSQL_SSL", "") == "1"},
            "flask": {"secret_key": os.environ.get("SECRET_KEY")},
        }
    for p in (BASE_DIR / "config.toml", BASE_DIR / ".streamlit" / "secrets.toml"):
        if p.exists():
            with open(p, "rb") as f:
                return tomllib.load(f)
    # Sin configuración la app igual arranca y muestra un aviso en lugar de caerse
    return {"mysql": None, "flask": {"secret_key": os.environ.get("SECRET_KEY")}}


CONFIG = load_config()


# ======================================================
# Conexión
# ======================================================
def get_conn(autocommit=False):
    cfg = CONFIG["mysql"]
    if not cfg:
        raise pymysql.err.OperationalError(
            2003, "Base de datos no configurada: define MYSQL_HOST, MYSQL_PORT, MYSQL_USER y MYSQL_PASSWORD")
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=autocommit,
        ssl={"ssl": {}} if cfg.get("ssl") else None,
    )


# Registro de las sentencias SQL ejecutadas (lo usa el panel "Ver SQL" de la interfaz)
_oyentes = []


def on_sql(fn):
    _oyentes.append(fn)


def _emitir(texto):
    for fn in _oyentes:
        fn(texto)


def _log(cur, sql, params):
    if _oyentes:
        try:
            texto = cur.mogrify(sql, params or ())
        except Exception:
            texto = sql
        _emitir(" ".join(texto.split()))


class _CursorLog:
    """Envuelve el cursor para registrar cada execute dentro de una transacción."""

    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        _log(self._cur, sql, params)
        return self._cur.execute(sql, params or ())

    def __getattr__(self, nombre):
        return getattr(self._cur, nombre)


# Conexión compartida: la app web puede entregar una sola conexión por petición
# (así una página con varias consultas no abre una conexión nueva para cada una)
_proveedor = None


def usar_conexion_compartida(fn):
    global _proveedor
    _proveedor = fn


def _compartida():
    return _proveedor() if _proveedor else None


def query(sql, params=None):
    conn = _compartida()
    propia = conn is None
    if propia:
        conn = get_conn()
    try:
        with conn.cursor() as cur:
            _log(cur, sql, params)
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        if propia:
            conn.close()


def one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


def run_tx(fn):
    """Ejecuta fn(cursor) dentro de una transacción (commit / rollback)."""
    conn = _compartida()
    propia = conn is None
    if propia:
        conn = get_conn()
    try:
        conn.begin()
        _emitir("START TRANSACTION;")
        with conn.cursor() as cur:
            res = fn(_CursorLog(cur))
        conn.commit()
        _emitir("COMMIT;")
        return res
    except Exception:
        conn.rollback()
        _emitir("ROLLBACK;")
        raise
    finally:
        if propia:
            conn.close()


def execute(sql, params=None):
    return run_tx(lambda cur: cur.execute(sql, params or ()))


def mensaje_error(e):
    """Traduce errores de MySQL a mensajes entendibles."""
    msg = str(e)
    if "Duplicate entry" in msg:
        return "Ya existe un registro con ese valor único (código, ISBN, correo o código de barras)."
    if "foreign key constraint" in msg.lower():
        return "No se puede eliminar: tiene registros relacionados (ejemplares o préstamos)."
    return f"Error de base de datos: {msg}"


# ======================================================
# Configuración del negocio
# ======================================================
def cfg_val(clave, default):
    r = one("SELECT valor FROM configuracion WHERE clave=%s", (clave,))
    return r["valor"] if r else str(default)


def tarifa_dia():
    return Decimal(cfg_val("tarifa_multa_dia", 2000))


def dias_prestamo():
    return int(cfg_val("dias_prestamo", 7))


# ======================================================
# Autenticación
# ======================================================
def hash_pwd(pwd, salt=None):
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", pwd.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"{salt}${h}"


def check_pwd(pwd, stored):
    salt = stored.split("$")[0]
    return hmac.compare_digest(hash_pwd(pwd, salt), stored)


def autenticar_personal(login, clave):
    r = one("SELECT * FROM personal WHERE login=%s", (login,))
    if r and check_pwd(clave, r["clave_hash"]):
        return {"tipo": "personal", "id": r["id_personal"], "nombre": r["nombres"], "rol": r["rol"]}
    return None


def autenticar_usuario(codigo, identificacion):
    r = one("SELECT * FROM usuario WHERE codigo=%s AND identificacion=%s", (codigo, identificacion))
    if r:
        return {"tipo": "usuario", "id": r["id_usuario"], "nombre": r["nombres"], "rol": r["rol"]}
    return None


# ======================================================
# Catálogo / libros
# ======================================================
# Categoría principal de un libro (alias l): da el color de su lomo en la interfaz
CAT_SQL = """(SELECT MIN(c.nombre) FROM libro_categoria lc JOIN categoria c
                ON c.id_categoria=lc.id_categoria WHERE lc.isbn=l.isbn) AS categoria"""

BASE_LIBROS = """
SELECT l.isbn, l.titulo,
  (SELECT GROUP_CONCAT(a.nombre ORDER BY a.nombre SEPARATOR ', ') FROM libro_autor la
     JOIN autor a ON a.id_autor = la.id_autor WHERE la.isbn = l.isbn) AS autores,
  e.nombre AS editorial, l.anio,
  (SELECT GROUP_CONCAT(c.nombre ORDER BY c.nombre SEPARATOR ', ') FROM libro_categoria lc
     JOIN categoria c ON c.id_categoria = lc.id_categoria WHERE lc.isbn = l.isbn) AS categorias,
  (SELECT COUNT(*) FROM ejemplar x WHERE x.isbn = l.isbn AND x.estado='disponible') AS disponibles,
  (SELECT COUNT(*) FROM ejemplar x WHERE x.isbn = l.isbn) AS total_ejemplares,
  l.descripcion
FROM libro l LEFT JOIN editorial e ON e.id_editorial = l.id_editorial
"""


def buscar_libros(titulo="", autor="", isbn="", categoria="", solo_disponibles=False):
    sql = BASE_LIBROS + " WHERE l.titulo LIKE %s AND l.isbn LIKE %s"
    params = [f"%{titulo}%", f"%{isbn}%"]
    if autor:
        sql += (" AND EXISTS (SELECT 1 FROM libro_autor la JOIN autor a ON a.id_autor=la.id_autor"
                " WHERE la.isbn=l.isbn AND a.nombre LIKE %s)")
        params.append(f"%{autor}%")
    if categoria:
        sql += (" AND EXISTS (SELECT 1 FROM libro_categoria lc JOIN categoria c ON c.id_categoria=lc.id_categoria"
                " WHERE lc.isbn=l.isbn AND c.nombre = %s)")
        params.append(categoria)
    if solo_disponibles:
        sql += " AND EXISTS (SELECT 1 FROM ejemplar x WHERE x.isbn=l.isbn AND x.estado='disponible')"
    sql += " ORDER BY l.titulo"
    return query(sql, params)


def get_libro(isbn):
    return one(BASE_LIBROS + " WHERE l.isbn=%s", (isbn,))


def nombres(tabla):
    assert tabla in ("editorial", "autor", "categoria")
    return [r["nombre"] for r in query(f"SELECT nombre FROM {tabla} ORDER BY nombre")]


def _get_or_create(cur, tabla, idcol, nombre):
    cur.execute(f"SELECT {idcol} FROM {tabla} WHERE nombre=%s", (nombre,))
    r = cur.fetchone()
    if r:
        return r[idcol]
    cur.execute(f"INSERT INTO {tabla}(nombre) VALUES (%s)", (nombre,))
    return cur.lastrowid


def guardar_libro(d, nuevo):
    def tx(cur):
        id_ed = _get_or_create(cur, "editorial", "id_editorial", d["editorial"]) if d["editorial"] else None
        if nuevo:
            cur.execute("INSERT INTO libro (isbn,titulo,id_editorial,anio,descripcion) VALUES (%s,%s,%s,%s,%s)",
                        (d["isbn"], d["titulo"], id_ed, d["anio"], d["descripcion"]))
        else:
            cur.execute("UPDATE libro SET titulo=%s,id_editorial=%s,anio=%s,descripcion=%s WHERE isbn=%s",
                        (d["titulo"], id_ed, d["anio"], d["descripcion"], d["isbn"]))
            cur.execute("DELETE FROM libro_autor WHERE isbn=%s", (d["isbn"],))
            cur.execute("DELETE FROM libro_categoria WHERE isbn=%s", (d["isbn"],))
        for a in dict.fromkeys(d["autores"]):
            cur.execute("INSERT INTO libro_autor VALUES (%s,%s)",
                        (d["isbn"], _get_or_create(cur, "autor", "id_autor", a)))
        for c in dict.fromkeys(d["categorias"]):
            cur.execute("INSERT INTO libro_categoria VALUES (%s,%s)",
                        (d["isbn"], _get_or_create(cur, "categoria", "id_categoria", c)))
    run_tx(tx)


def eliminar_libro(isbn):
    execute("DELETE FROM libro WHERE isbn=%s", (isbn,))


# ======================================================
# Ejemplares
# ======================================================
EST_EJ = ["disponible", "prestado", "perdido"]


def listar_ejemplares(estado="", q=""):
    sql = """SELECT e.*, l.titulo FROM ejemplar e JOIN libro l ON l.isbn=e.isbn
             WHERE (l.titulo LIKE %s OR e.codigo_barras LIKE %s OR e.isbn LIKE %s)"""
    params = [f"%{q}%"] * 3
    if estado:
        sql += " AND e.estado=%s"
        params.append(estado)
    return query(sql + " ORDER BY l.titulo, e.codigo_barras", params)


def get_ejemplar(id_ejemplar):
    return one("SELECT e.*, l.titulo FROM ejemplar e JOIN libro l ON l.isbn=e.isbn WHERE e.id_ejemplar=%s",
               (id_ejemplar,))


def crear_ejemplar(cod, isbn, ubi, est):
    execute("INSERT INTO ejemplar (codigo_barras,isbn,ubicacion,estado) VALUES (%s,%s,%s,%s)",
            (cod, isbn, ubi, est))


def actualizar_ejemplar(id_ejemplar, cod, isbn, ubi, est):
    execute("UPDATE ejemplar SET codigo_barras=%s,isbn=%s,ubicacion=%s,estado=%s WHERE id_ejemplar=%s",
            (cod, isbn, ubi, est, id_ejemplar))


def eliminar_ejemplar(id_ejemplar):
    execute("DELETE FROM ejemplar WHERE id_ejemplar=%s", (id_ejemplar,))


def libros_simple():
    return query("SELECT isbn, titulo FROM libro ORDER BY titulo")


# ======================================================
# Usuarios
# ======================================================
def listar_usuarios(q="", rol="", estado=""):
    sql = "SELECT * FROM usuario WHERE (nombres LIKE %s OR codigo LIKE %s OR correo LIKE %s)"
    params = [f"%{q}%"] * 3
    if rol:
        sql += " AND rol=%s"
        params.append(rol)
    if estado:
        sql += " AND estado=%s"
        params.append(estado)
    return query(sql + " ORDER BY nombres", params)


def get_usuario(id_usuario):
    return one("SELECT * FROM usuario WHERE id_usuario=%s", (id_usuario,))


def crear_usuario(d):
    execute("""INSERT INTO usuario (codigo,identificacion,nombres,correo,rol,carrera,estado)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (d["codigo"], d["identificacion"], d["nombres"], d["correo"], d["rol"], d["carrera"], d["estado"]))


def actualizar_usuario(id_usuario, d):
    execute("""UPDATE usuario SET codigo=%s,identificacion=%s,nombres=%s,correo=%s,
               rol=%s,carrera=%s,estado=%s WHERE id_usuario=%s""",
            (d["codigo"], d["identificacion"], d["nombres"], d["correo"], d["rol"], d["carrera"],
             d["estado"], id_usuario))


def eliminar_usuario(id_usuario):
    execute("DELETE FROM usuario WHERE id_usuario=%s", (id_usuario,))


def historial_usuario(id_usuario):
    return query("""SELECT p.id_prestamo, l.titulo, l.isbn, ej.codigo_barras, p.estado, p.fecha_solicitud, """ + CAT_SQL + """,
                           p.fecha_prestamo, p.fecha_vencimiento, p.fecha_devolucion,
                           d.dias_retraso, d.multa, d.condicion, d.observaciones
                    FROM prestamo p JOIN libro l ON l.isbn=p.isbn
                    LEFT JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                    LEFT JOIN devolucion d ON d.id_prestamo=p.id_prestamo
                    WHERE p.id_usuario=%s ORDER BY p.fecha_solicitud DESC""", (id_usuario,))


# ======================================================
# Préstamos
# ======================================================
def solicitar_prestamo(id_usuario, isbn):
    max_p = int(cfg_val("max_prestamos", 3))

    def tx(cur):
        cur.execute("SELECT estado FROM usuario WHERE id_usuario=%s", (id_usuario,))
        u = cur.fetchone()
        if not u or u["estado"] != "activo":
            raise ValueError("Tu usuario está bloqueado; no puedes solicitar préstamos.")
        cur.execute("SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND isbn=%s "
                    "AND estado IN ('solicitado','activo')", (id_usuario, isbn))
        if cur.fetchone()["n"] > 0:
            raise ValueError("Ya tienes una solicitud o un préstamo vigente de este libro.")
        cur.execute("SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND estado IN ('solicitado','activo')",
                    (id_usuario,))
        if cur.fetchone()["n"] >= max_p:
            raise ValueError(f"Alcanzaste el máximo de {max_p} préstamos o solicitudes simultáneos.")
        cur.execute("SELECT COUNT(*) AS n FROM ejemplar WHERE isbn=%s AND estado='disponible'", (isbn,))
        if cur.fetchone()["n"] == 0:
            raise ValueError("Este libro no tiene ejemplares disponibles en este momento.")
        cur.execute("INSERT INTO prestamo (id_usuario, isbn, estado) VALUES (%s,%s,'solicitado')",
                    (id_usuario, isbn))
    run_tx(tx)


def _validar_y_prestar(cur, id_usuario, id_ejemplar, id_personal, f_prest, f_venc, id_prestamo=None, isbn=None):
    cur.execute("SELECT estado FROM usuario WHERE id_usuario=%s FOR UPDATE", (id_usuario,))
    u = cur.fetchone()
    if not u or u["estado"] != "activo":
        raise ValueError("El usuario no está activo; no se puede prestar.")
    cur.execute("SELECT estado, isbn FROM ejemplar WHERE id_ejemplar=%s FOR UPDATE", (id_ejemplar,))
    e = cur.fetchone()
    if not e or e["estado"] != "disponible":
        raise ValueError("El ejemplar ya no está disponible.")
    if isbn and e["isbn"] != isbn:
        raise ValueError("El ejemplar no corresponde al libro solicitado.")
    if f_venc <= f_prest:
        raise ValueError("La fecha de vencimiento debe ser posterior a la del préstamo.")
    cur.execute("UPDATE ejemplar SET estado='prestado' WHERE id_ejemplar=%s", (id_ejemplar,))
    if id_prestamo:
        cur.execute("""UPDATE prestamo SET id_ejemplar=%s, id_personal=%s, fecha_prestamo=%s,
                       fecha_vencimiento=%s, estado='activo' WHERE id_prestamo=%s AND estado='solicitado'""",
                    (id_ejemplar, id_personal, f_prest, f_venc, id_prestamo))
        if cur.rowcount == 0:
            raise ValueError("La solicitud ya fue atendida por otra persona.")
    else:
        cur.execute("""INSERT INTO prestamo (id_usuario,isbn,id_ejemplar,id_personal,fecha_prestamo,
                       fecha_vencimiento,estado) VALUES (%s,%s,%s,%s,%s,%s,'activo')""",
                    (id_usuario, e["isbn"], id_ejemplar, id_personal, f_prest, f_venc))


def solicitudes_pendientes():
    sols = query("""SELECT p.id_prestamo, p.id_usuario, p.isbn, u.nombres, u.codigo, u.rol, """ + CAT_SQL + """,
                           u.estado AS estado_usuario, l.titulo, p.fecha_solicitud
                    FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                    JOIN libro l ON l.isbn=p.isbn
                    WHERE p.estado='solicitado' ORDER BY p.fecha_solicitud""")
    for s in sols:
        s["ejemplares"] = query("SELECT id_ejemplar, codigo_barras, ubicacion FROM ejemplar "
                                "WHERE isbn=%s AND estado='disponible' ORDER BY codigo_barras", (s["isbn"],))
    return sols


def aprobar_solicitud(id_prestamo, id_ejemplar, id_personal, f_venc):
    s = one("SELECT id_usuario, isbn FROM prestamo WHERE id_prestamo=%s", (id_prestamo,))
    if not s:
        raise ValueError("La solicitud no existe.")
    run_tx(lambda cur: _validar_y_prestar(cur, s["id_usuario"], id_ejemplar, id_personal, date.today(), f_venc,
                                          id_prestamo=id_prestamo, isbn=s["isbn"]))


def rechazar_solicitud(id_prestamo, id_personal):
    execute("UPDATE prestamo SET estado='rechazado', id_personal=%s WHERE id_prestamo=%s AND estado='solicitado'",
            (id_personal, id_prestamo))


def prestamo_directo(id_usuario, id_ejemplar, id_personal, f_prest, f_venc):
    run_tx(lambda cur: _validar_y_prestar(cur, id_usuario, id_ejemplar, id_personal, f_prest, f_venc))


def ejemplares_disponibles():
    return query("""SELECT e.id_ejemplar, e.codigo_barras, e.ubicacion, l.titulo FROM ejemplar e
                    JOIN libro l ON l.isbn=e.isbn WHERE e.estado='disponible' ORDER BY l.titulo""")


def prestamos_activos():
    return query("""SELECT p.id_prestamo, p.id_ejemplar, u.nombres AS usuario, u.codigo, l.titulo, l.isbn, """ + CAT_SQL + """,
                           ej.codigo_barras, p.fecha_prestamo, p.fecha_vencimiento,
                           GREATEST(DATEDIFF(CURDATE(), p.fecha_vencimiento),0) AS dias_retraso,
                           GREATEST(DATEDIFF(CURDATE(), p.fecha_vencimiento),0) * %s AS multa_estimada
                    FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                    JOIN libro l ON l.isbn=p.isbn JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                    WHERE p.estado='activo' ORDER BY p.fecha_vencimiento""", (tarifa_dia(),))


# ======================================================
# Devoluciones
# ======================================================
CONDICIONES = ["bueno", "dañado", "páginas faltantes"]


def registrar_devolucion(id_prestamo, id_personal, f_dev, condicion, obs):
    tarifa = tarifa_dia()

    def tx(cur):
        cur.execute("""SELECT estado, id_ejemplar, fecha_prestamo, fecha_vencimiento
                       FROM prestamo WHERE id_prestamo=%s FOR UPDATE""", (id_prestamo,))
        p = cur.fetchone()
        if not p or p["estado"] != "activo":
            raise ValueError("El préstamo ya no está activo.")
        if f_dev > date.today():
            raise ValueError("La fecha de devolución no puede ser futura.")
        if f_dev < p["fecha_prestamo"]:
            raise ValueError("La devolución no puede ser anterior a la fecha del préstamo.")
        retraso = max((f_dev - p["fecha_vencimiento"]).days, 0)
        multa = retraso * tarifa
        cur.execute("""INSERT INTO devolucion (id_prestamo,id_personal,fecha_devolucion,dias_retraso,
                       multa,condicion,observaciones) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (id_prestamo, id_personal, f_dev, retraso, multa, condicion, obs or None))
        cur.execute("UPDATE prestamo SET estado='devuelto', fecha_devolucion=%s WHERE id_prestamo=%s",
                    (f_dev, id_prestamo))
        cur.execute("UPDATE ejemplar SET estado='disponible' WHERE id_ejemplar=%s", (p["id_ejemplar"],))
        return retraso, multa
    return run_tx(tx)


def ultimas_devoluciones(limit=15):
    return query("""SELECT d.id_devolucion, d.id_prestamo, l.titulo, u.nombres AS usuario, ej.codigo_barras, d.fecha_devolucion,
                           d.dias_retraso, d.multa, d.condicion, d.observaciones
                    FROM devolucion d JOIN prestamo p ON p.id_prestamo=d.id_prestamo
                    JOIN libro l ON l.isbn=p.isbn JOIN usuario u ON u.id_usuario=p.id_usuario
                    LEFT JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                    ORDER BY d.id_devolucion DESC LIMIT %s""", (limit,))


# ======================================================
# Reportes
# ======================================================
def libros_mas_prestados(ini, fin, limit=10):
    return query("""SELECT l.titulo, l.isbn, COUNT(*) AS prestamos, """ + CAT_SQL + """
                    FROM prestamo p JOIN libro l ON l.isbn=p.isbn
                    WHERE p.estado IN ('activo','devuelto') AND p.fecha_prestamo BETWEEN %s AND %s
                    GROUP BY l.isbn, l.titulo ORDER BY prestamos DESC, l.titulo LIMIT %s""", (ini, fin, limit))


def usuarios_mas_prestamos(ini, fin, limit=10):
    return query("""SELECT u.codigo, u.nombres, u.rol, COUNT(*) AS prestamos
                    FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                    WHERE p.estado IN ('activo','devuelto') AND p.fecha_prestamo BETWEEN %s AND %s
                    GROUP BY u.id_usuario, u.codigo, u.nombres, u.rol
                    ORDER BY prestamos DESC, u.nombres LIMIT %s""", (ini, fin, limit))


def prestamos_por_mes(meses=12):
    """Cantidad de préstamos por mes (últimos N meses, incluye los meses sin préstamos)."""
    rows = query("""SELECT DATE_FORMAT(fecha_prestamo, '%%Y-%%m') AS mes, COUNT(*) AS prestamos
                    FROM prestamo WHERE estado IN ('activo','devuelto')
                      AND fecha_prestamo >= DATE_SUB(DATE_FORMAT(CURDATE(), '%%Y-%%m-01'), INTERVAL %s MONTH)
                    GROUP BY mes ORDER BY mes""", (meses - 1,))
    cuenta = {r["mes"]: r["prestamos"] for r in rows}
    hoy = date.today()
    salida = []
    for i in range(meses - 1, -1, -1):
        y, m = divmod(hoy.year * 12 + hoy.month - 1 - i, 12)
        clave = f"{y}-{m + 1:02d}"
        salida.append({"mes": clave, "anio": y, "num": m + 1, "prestamos": cuenta.get(clave, 0)})
    return salida


def prestamos_por_dia(semanas=26):
    """Préstamos por día de las últimas N semanas (para el mapa de calor)."""
    rows = query("""SELECT fecha_prestamo AS dia, COUNT(*) AS n FROM prestamo
                    WHERE estado IN ('activo','devuelto')
                      AND fecha_prestamo >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    GROUP BY fecha_prestamo""", (semanas * 7,))
    return {r["dia"]: r["n"] for r in rows}


def prestamos_de_libro(isbn, limit=30):
    return query("""SELECT p.id_prestamo, p.estado, p.fecha_solicitud, p.fecha_prestamo, p.fecha_vencimiento,
                           p.fecha_devolucion, u.nombres, u.codigo, ej.codigo_barras, d.multa, d.condicion
                    FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                    LEFT JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                    LEFT JOIN devolucion d ON d.id_prestamo=p.id_prestamo
                    WHERE p.isbn=%s ORDER BY p.fecha_solicitud DESC LIMIT %s""", (isbn, limit))


def ejemplares_de_libro(isbn):
    return query("SELECT * FROM ejemplar WHERE isbn=%s ORDER BY codigo_barras", (isbn,))


def get_prestamo_detalle(id_prestamo):
    """Todo lo necesario para imprimir el comprobante de un préstamo o devolución."""
    return one("""SELECT p.*, u.nombres, u.codigo, u.identificacion, u.correo, u.rol, u.carrera,
                         l.titulo, ej.codigo_barras, ej.ubicacion, pe.nombres AS aprobado_por,
                         d.fecha_devolucion AS f_dev, d.dias_retraso, d.multa, d.condicion, d.observaciones,
                         pd.nombres AS recibido_por,
                         (SELECT GROUP_CONCAT(a.nombre ORDER BY a.nombre SEPARATOR ', ') FROM libro_autor la
                            JOIN autor a ON a.id_autor=la.id_autor WHERE la.isbn=l.isbn) AS autores
                  FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                  JOIN libro l ON l.isbn=p.isbn
                  LEFT JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                  LEFT JOIN personal pe ON pe.id_personal=p.id_personal
                  LEFT JOIN devolucion d ON d.id_prestamo=p.id_prestamo
                  LEFT JOIN personal pd ON pd.id_personal=d.id_personal
                  WHERE p.id_prestamo=%s""", (id_prestamo,))


def inventario_por_estado():
    rows = query("SELECT estado, COUNT(*) AS cantidad FROM ejemplar GROUP BY estado")
    inv = {e: 0 for e in EST_EJ}
    for r in rows:
        inv[r["estado"]] = r["cantidad"]
    return inv


def estante(limit=80):
    """Cada ejemplar con su libro y categoría principal (para dibujar el estante)."""
    return query("""SELECT e.id_ejemplar, e.codigo_barras, e.estado, l.titulo, l.isbn,
                           (SELECT MIN(c.nombre) FROM libro_categoria lc JOIN categoria c
                              ON c.id_categoria=lc.id_categoria WHERE lc.isbn=l.isbn) AS categoria
                    FROM ejemplar e JOIN libro l ON l.isbn=e.isbn
                    ORDER BY categoria, l.titulo, e.codigo_barras LIMIT %s""", (limit,))


def resumen():
    r = one("""SELECT
                 (SELECT COUNT(*) FROM prestamo WHERE estado='solicitado') AS solicitudes,
                 (SELECT COUNT(*) FROM prestamo WHERE estado='activo') AS activos,
                 (SELECT COUNT(*) FROM prestamo WHERE estado='activo' AND fecha_vencimiento < CURDATE()) AS vencidos,
                 (SELECT COUNT(*) FROM libro) AS libros,
                 (SELECT COUNT(*) FROM usuario) AS usuarios""")
    r["inventario"] = inventario_por_estado()
    r["tarifa"] = tarifa_dia()
    return r
