import hashlib
import hmac
import os
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pymysql
import streamlit as st

st.set_page_config(page_title="Biblioteca Universitaria", page_icon="📚", layout="wide")


# ======================================================
# Base de datos
# ======================================================
def get_conn():
    cfg = st.secrets["mysql"]
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def query(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def run_tx(fn):
    """Ejecuta fn(cursor) dentro de una transacción (commit / rollback)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            res = fn(cur)
        conn.commit()
        return res
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql, params=None):
    return run_tx(lambda cur: cur.execute(sql, params or ()))


def to_df(rows):
    df = pd.DataFrame(rows)
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, Decimal)).any():
            df[c] = df[c].astype(float)
    return df


def show(rows, empty="Sin resultados."):
    if rows:
        st.dataframe(to_df(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def cfg_val(clave, default):
    r = query("SELECT valor FROM configuracion WHERE clave=%s", (clave,))
    return r[0]["valor"] if r else str(default)


def tarifa_dia():
    return float(cfg_val("tarifa_multa_dia", 2000))


def err(e):
    msg = str(e)
    if "Duplicate entry" in msg:
        st.error("Ya existe un registro con ese valor único (código, ISBN, correo, etc.).")
    elif "foreign key constraint" in msg.lower():
        st.error("No se puede eliminar/modificar: hay registros relacionados (ejemplares o préstamos).")
    else:
        st.error(f"Error: {msg}")


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


def login_sidebar():
    if "auth" in st.session_state:
        a = st.session_state["auth"]
        st.sidebar.success(f"👤 {a['nombre']}\n\nRol: {a['rol']}")
        if st.sidebar.button("Cerrar sesión"):
            del st.session_state["auth"]
            st.rerun()
        return True

    st.sidebar.subheader("Iniciar sesión")
    modo = st.sidebar.radio("Ingresar como", ["Usuario", "Personal"], horizontal=True)
    with st.sidebar.form("login"):
        if modo == "Personal":
            a1 = st.text_input("Login")
            a2 = st.text_input("Clave", type="password")
        else:
            a1 = st.text_input("Código de usuario")
            a2 = st.text_input("Identificación", type="password")
        ok = st.form_submit_button("Entrar")
    if ok:
        try:
            if modo == "Personal":
                r = query("SELECT * FROM personal WHERE login=%s", (a1,))
                if r and check_pwd(a2, r[0]["clave_hash"]):
                    st.session_state["auth"] = {
                        "tipo": "personal", "id": r[0]["id_personal"],
                        "nombre": r[0]["nombres"], "rol": r[0]["rol"],
                    }
                    st.rerun()
            else:
                r = query("SELECT * FROM usuario WHERE codigo=%s AND identificacion=%s", (a1, a2))
                if r:
                    st.session_state["auth"] = {
                        "tipo": "usuario", "id": r[0]["id_usuario"],
                        "nombre": r[0]["nombres"], "rol": r[0]["rol"],
                    }
                    st.rerun()
            st.sidebar.error("Credenciales incorrectas")
        except Exception as e:
            st.sidebar.error(f"No se pudo conectar a la base de datos: {e}")
    return False


# ======================================================
# Catálogo / búsqueda
# ======================================================
BASE_LIBROS = """
SELECT l.isbn, l.titulo,
  (SELECT GROUP_CONCAT(a.nombre SEPARATOR ', ') FROM libro_autor la
     JOIN autor a ON a.id_autor = la.id_autor WHERE la.isbn = l.isbn) AS autores,
  e.nombre AS editorial, l.anio,
  (SELECT GROUP_CONCAT(c.nombre SEPARATOR ', ') FROM libro_categoria lc
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
                " WHERE lc.isbn=l.isbn AND c.nombre LIKE %s)")
        params.append(f"%{categoria}%")
    sql += " ORDER BY l.titulo"
    rows = query(sql, params)
    if solo_disponibles:
        rows = [r for r in rows if r["disponibles"] > 0]
    return rows


def pg_catalogo():
    st.header("📖 Catálogo de libros")
    c1, c2, c3, c4 = st.columns(4)
    titulo = c1.text_input("Título")
    autor = c2.text_input("Autor")
    isbn = c3.text_input("ISBN")
    cat = c4.text_input("Categoría / tema")
    solo = st.checkbox("Solo con ejemplares disponibles")
    rows = buscar_libros(titulo, autor, isbn, cat, solo)
    show(rows, "No se encontraron libros.")

    auth = st.session_state["auth"]
    if auth["tipo"] == "usuario" and rows:
        st.divider()
        st.subheader("Solicitar préstamo")
        disp = [r for r in rows if r["disponibles"] > 0]
        if not disp:
            st.warning("Ninguno de los libros listados tiene ejemplares disponibles.")
            return
        opc = {f"{r['titulo']} ({r['isbn']}) – {r['disponibles']} disp.": r["isbn"] for r in disp}
        sel = st.selectbox("Libro", list(opc))
        if st.button("Solicitar préstamo", type="primary"):
            try:
                solicitar_prestamo(auth["id"], opc[sel])
                st.success("Solicitud enviada. Un bibliotecario debe aprobarla.")
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                err(e)


def solicitar_prestamo(id_usuario, isbn):
    def tx(cur):
        cur.execute("SELECT estado FROM usuario WHERE id_usuario=%s", (id_usuario,))
        u = cur.fetchone()
        if not u or u["estado"] != "activo":
            raise ValueError("Tu usuario está bloqueado; no puedes solicitar préstamos.")
        cur.execute("SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND isbn=%s "
                    "AND estado IN ('solicitado','activo')", (id_usuario, isbn))
        if cur.fetchone()["n"] > 0:
            raise ValueError("Ya tienes una solicitud o préstamo vigente de este libro.")
        cur.execute("SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND estado IN ('solicitado','activo')",
                    (id_usuario,))
        if cur.fetchone()["n"] >= int(cfg_val("max_prestamos", 3)):
            raise ValueError("Alcanzaste el máximo de préstamos/solicitudes simultáneos.")
        cur.execute("INSERT INTO prestamo (id_usuario, isbn, estado) VALUES (%s,%s,'solicitado')",
                    (id_usuario, isbn))
    run_tx(tx)


# ======================================================
# CRUD Libros
# ======================================================
def get_or_create(cur, tabla, idcol, nombre):
    cur.execute(f"SELECT {idcol} FROM {tabla} WHERE nombre=%s", (nombre,))
    r = cur.fetchone()
    if r:
        return r[idcol]
    cur.execute(f"INSERT INTO {tabla}(nombre) VALUES (%s)", (nombre,))
    return cur.lastrowid


def nombres(tabla):
    return [r["nombre"] for r in query(f"SELECT nombre FROM {tabla} ORDER BY nombre")]


def split_nuevos(txt):
    return [x.strip() for x in txt.split(",") if x.strip()]


def guardar_libro(d, nuevo):
    def tx(cur):
        id_ed = get_or_create(cur, "editorial", "id_editorial", d["editorial"]) if d["editorial"] else None
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
                        (d["isbn"], get_or_create(cur, "autor", "id_autor", a)))
        for c in dict.fromkeys(d["categorias"]):
            cur.execute("INSERT INTO libro_categoria VALUES (%s,%s)",
                        (d["isbn"], get_or_create(cur, "categoria", "id_categoria", c)))
    run_tx(tx)


def form_libro(prefix, actual=None):
    """Dibuja los campos del libro y devuelve dict (o None si falta algo)."""
    actual = actual or {}
    isbn = st.text_input("ISBN", value=actual.get("isbn", ""), disabled=bool(actual), key=f"{prefix}_isbn")
    titulo = st.text_input("Título", value=actual.get("titulo", ""), key=f"{prefix}_titulo")
    eds = [""] + nombres("editorial")
    ed_act = actual.get("editorial") or ""
    ed = st.selectbox("Editorial", eds, index=eds.index(ed_act) if ed_act in eds else 0, key=f"{prefix}_ed")
    ed_new = st.text_input("…o nueva editorial", key=f"{prefix}_ednew")
    anio = st.number_input("Año", 0, 2100, int(actual.get("anio") or 2020), key=f"{prefix}_anio")
    desc = st.text_area("Descripción", value=actual.get("descripcion") or "", key=f"{prefix}_desc")
    aut_all = nombres("autor")
    aut_def = [a for a in (actual.get("autores") or "").split(", ") if a in aut_all]
    autores = st.multiselect("Autores", aut_all, default=aut_def, key=f"{prefix}_aut")
    aut_new = st.text_input("…y/o autores nuevos (separados por coma)", key=f"{prefix}_autnew")
    cat_all = nombres("categoria")
    cat_def = [c for c in (actual.get("categorias") or "").split(", ") if c in cat_all]
    cats = st.multiselect("Categorías", cat_all, default=cat_def, key=f"{prefix}_cat")
    cat_new = st.text_input("…y/o categorías nuevas (separadas por coma)", key=f"{prefix}_catnew")
    return {
        "isbn": isbn.strip(), "titulo": titulo.strip(),
        "editorial": (ed_new.strip() or ed),
        "anio": int(anio) or None, "descripcion": desc.strip(),
        "autores": autores + split_nuevos(aut_new),
        "categorias": cats + split_nuevos(cat_new),
    }


def pg_libros():
    st.header("📚 Gestión de libros")
    t1, t2, t3 = st.tabs(["Listado", "Crear", "Editar / Eliminar"])
    with t1:
        show(query(BASE_LIBROS + " ORDER BY l.titulo"))
    with t2:
        d = form_libro("new")
        if st.button("Guardar libro", type="primary", key="save_new"):
            if not d["isbn"] or not d["titulo"] or not d["autores"]:
                st.error("ISBN, título y al menos un autor son obligatorios.")
            else:
                try:
                    guardar_libro(d, True)
                    st.success("Libro creado.")
                except Exception as e:
                    err(e)
    with t3:
        libros = query(BASE_LIBROS + " ORDER BY l.titulo")
        if not libros:
            st.info("No hay libros.")
            return
        opc = {f"{l['titulo']} ({l['isbn']})": l for l in libros}
        sel = opc[st.selectbox("Libro", list(opc))]
        d = form_libro(f"edit_{sel['isbn']}", sel)
        d["isbn"] = sel["isbn"]
        c1, c2 = st.columns(2)
        if c1.button("Actualizar", type="primary", key="upd_libro"):
            if not d["titulo"] or not d["autores"]:
                st.error("Título y al menos un autor son obligatorios.")
            else:
                try:
                    guardar_libro(d, False)
                    st.success("Libro actualizado.")
                except Exception as e:
                    err(e)
        if c2.button("Eliminar", key="del_libro"):
            try:
                execute("DELETE FROM libro WHERE isbn=%s", (sel["isbn"],))
                st.success("Libro eliminado.")
                st.rerun()
            except Exception as e:
                err(e)


# ======================================================
# CRUD Ejemplares
# ======================================================
EST_EJ = ["disponible", "prestado", "perdido"]


def pg_ejemplares():
    st.header("🏷️ Gestión de ejemplares")
    t1, t2, t3 = st.tabs(["Listado", "Crear", "Editar / Eliminar"])
    libros = query("SELECT isbn, titulo FROM libro ORDER BY titulo")
    opc_l = {f"{l['titulo']} ({l['isbn']})": l["isbn"] for l in libros}
    with t1:
        show(query("""SELECT e.id_ejemplar, e.codigo_barras, l.titulo, e.isbn, e.ubicacion, e.estado
                      FROM ejemplar e JOIN libro l ON l.isbn=e.isbn ORDER BY l.titulo, e.codigo_barras"""))
    with t2:
        with st.form("nuevo_ej", clear_on_submit=True):
            cod = st.text_input("Código de barras / ID")
            lib = st.selectbox("Libro", list(opc_l))
            ubi = st.text_input("Ubicación (sala/estante)")
            est = st.selectbox("Estado", EST_EJ)
            ok = st.form_submit_button("Crear ejemplar")
        if ok:
            if not cod.strip() or not ubi.strip():
                st.error("Código y ubicación son obligatorios.")
            else:
                try:
                    execute("INSERT INTO ejemplar (codigo_barras,isbn,ubicacion,estado) VALUES (%s,%s,%s,%s)",
                            (cod.strip(), opc_l[lib], ubi.strip(), est))
                    st.success("Ejemplar creado.")
                except Exception as e:
                    err(e)
    with t3:
        ejs = query("""SELECT e.*, l.titulo FROM ejemplar e JOIN libro l ON l.isbn=e.isbn
                       ORDER BY e.codigo_barras""")
        if not ejs:
            st.info("No hay ejemplares.")
            return
        opc = {f"{e['codigo_barras']} – {e['titulo']}": e for e in ejs}
        e = opc[st.selectbox("Ejemplar", list(opc))]
        k = f"ej_{e['id_ejemplar']}"
        cod = st.text_input("Código de barras", e["codigo_barras"], key=k + "c")
        keys = list(opc_l)
        idx = list(opc_l.values()).index(e["isbn"])
        lib = st.selectbox("Libro", keys, index=idx, key=k + "l")
        ubi = st.text_input("Ubicación", e["ubicacion"], key=k + "u")
        est = st.selectbox("Estado", EST_EJ, index=EST_EJ.index(e["estado"]), key=k + "e")
        c1, c2 = st.columns(2)
        if c1.button("Actualizar", type="primary", key=k + "up"):
            try:
                execute("UPDATE ejemplar SET codigo_barras=%s,isbn=%s,ubicacion=%s,estado=%s WHERE id_ejemplar=%s",
                        (cod.strip(), opc_l[lib], ubi.strip(), est, e["id_ejemplar"]))
                st.success("Ejemplar actualizado.")
            except Exception as ex:
                err(ex)
        if c2.button("Eliminar", key=k + "del"):
            try:
                execute("DELETE FROM ejemplar WHERE id_ejemplar=%s", (e["id_ejemplar"],))
                st.success("Ejemplar eliminado.")
                st.rerun()
            except Exception as ex:
                err(ex)


# ======================================================
# CRUD Usuarios + historial
# ======================================================
def pg_usuarios():
    st.header("👥 Gestión de usuarios")
    t1, t2, t3, t4 = st.tabs(["Listado", "Crear", "Editar / Eliminar", "Historial de préstamos"])
    with t1:
        show(query("SELECT * FROM usuario ORDER BY nombres"))
    with t2:
        with st.form("nuevo_u", clear_on_submit=True):
            cod = st.text_input("Código")
            idf = st.text_input("Identificación")
            nom = st.text_input("Nombres")
            cor = st.text_input("Correo")
            rol = st.selectbox("Rol", ["estudiante", "docente"])
            car = st.text_input("Carrera (opcional)")
            est = st.selectbox("Estado", ["activo", "bloqueado"])
            ok = st.form_submit_button("Crear usuario")
        if ok:
            if not (cod.strip() and idf.strip() and nom.strip() and cor.strip()):
                st.error("Código, identificación, nombres y correo son obligatorios.")
            else:
                try:
                    execute("""INSERT INTO usuario (codigo,identificacion,nombres,correo,rol,carrera,estado)
                               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                            (cod.strip(), idf.strip(), nom.strip(), cor.strip(), rol, car.strip() or None, est))
                    st.success("Usuario creado.")
                except Exception as e:
                    err(e)
    with t3:
        us = query("SELECT * FROM usuario ORDER BY nombres")
        if not us:
            st.info("No hay usuarios.")
        else:
            opc = {f"{u['codigo']} – {u['nombres']}": u for u in us}
            u = opc[st.selectbox("Usuario", list(opc), key="sel_u_edit")]
            k = f"u_{u['id_usuario']}"
            cod = st.text_input("Código", u["codigo"], key=k + "c")
            idf = st.text_input("Identificación", u["identificacion"], key=k + "i")
            nom = st.text_input("Nombres", u["nombres"], key=k + "n")
            cor = st.text_input("Correo", u["correo"], key=k + "m")
            roles = ["estudiante", "docente"]
            rol = st.selectbox("Rol", roles, index=roles.index(u["rol"]), key=k + "r")
            car = st.text_input("Carrera", u["carrera"] or "", key=k + "ca")
            ests = ["activo", "bloqueado"]
            est = st.selectbox("Estado", ests, index=ests.index(u["estado"]), key=k + "e")
            c1, c2 = st.columns(2)
            if c1.button("Actualizar", type="primary", key=k + "up"):
                try:
                    execute("""UPDATE usuario SET codigo=%s,identificacion=%s,nombres=%s,correo=%s,
                               rol=%s,carrera=%s,estado=%s WHERE id_usuario=%s""",
                            (cod.strip(), idf.strip(), nom.strip(), cor.strip(), rol,
                             car.strip() or None, est, u["id_usuario"]))
                    st.success("Usuario actualizado.")
                except Exception as e:
                    err(e)
            if c2.button("Eliminar", key=k + "del"):
                try:
                    execute("DELETE FROM usuario WHERE id_usuario=%s", (u["id_usuario"],))
                    st.success("Usuario eliminado.")
                    st.rerun()
                except Exception as e:
                    err(e)
    with t4:
        us = query("SELECT id_usuario, codigo, nombres FROM usuario ORDER BY nombres")
        if us:
            opc = {f"{u['codigo']} – {u['nombres']}": u["id_usuario"] for u in us}
            show(historial_usuario(opc[st.selectbox("Usuario", list(opc), key="sel_u_hist")]),
                 "Este usuario no tiene préstamos.")


def historial_usuario(id_usuario):
    return query("""SELECT p.id_prestamo, l.titulo, ej.codigo_barras, p.estado, p.fecha_solicitud,
                           p.fecha_prestamo, p.fecha_vencimiento, p.fecha_devolucion,
                           d.dias_retraso, d.multa, d.condicion, d.observaciones
                    FROM prestamo p JOIN libro l ON l.isbn=p.isbn
                    LEFT JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                    LEFT JOIN devolucion d ON d.id_prestamo=p.id_prestamo
                    WHERE p.id_usuario=%s ORDER BY p.fecha_solicitud DESC""", (id_usuario,))


def pg_mis_prestamos():
    st.header("🗂️ Mis préstamos")
    show(historial_usuario(st.session_state["auth"]["id"]), "Aún no tienes préstamos.")


# ======================================================
# Préstamos (aprobación y registro directo)
# ======================================================
def validar_y_prestar(cur, id_usuario, id_ejemplar, id_personal, f_prest, f_venc, id_prestamo=None, isbn=None):
    cur.execute("SELECT estado FROM usuario WHERE id_usuario=%s FOR UPDATE", (id_usuario,))
    u = cur.fetchone()
    if not u or u["estado"] != "activo":
        raise ValueError("El usuario no está activo.")
    cur.execute("SELECT estado, isbn FROM ejemplar WHERE id_ejemplar=%s FOR UPDATE", (id_ejemplar,))
    e = cur.fetchone()
    if not e or e["estado"] != "disponible":
        raise ValueError("El ejemplar no está disponible.")
    if isbn and e["isbn"] != isbn:
        raise ValueError("El ejemplar no corresponde al libro solicitado.")
    if f_venc <= f_prest:
        raise ValueError("El vencimiento debe ser posterior al préstamo.")
    cur.execute("UPDATE ejemplar SET estado='prestado' WHERE id_ejemplar=%s", (id_ejemplar,))
    if id_prestamo:
        cur.execute("""UPDATE prestamo SET id_ejemplar=%s, id_personal=%s, fecha_prestamo=%s,
                       fecha_vencimiento=%s, estado='activo' WHERE id_prestamo=%s AND estado='solicitado'""",
                    (id_ejemplar, id_personal, f_prest, f_venc, id_prestamo))
    else:
        cur.execute("""INSERT INTO prestamo (id_usuario,isbn,id_ejemplar,id_personal,fecha_prestamo,
                       fecha_vencimiento,estado) VALUES (%s,%s,%s,%s,%s,%s,'activo')""",
                    (id_usuario, e["isbn"], id_ejemplar, id_personal, f_prest, f_venc))


def pg_prestamos():
    st.header("🤝 Préstamos")
    auth = st.session_state["auth"]
    dias = int(cfg_val("dias_prestamo", 7))
    t1, t2 = st.tabs(["Solicitudes pendientes", "Registrar préstamo directo"])

    with t1:
        sols = query("""SELECT p.id_prestamo, p.id_usuario, p.isbn, u.nombres, u.estado AS estado_usuario,
                               l.titulo, p.fecha_solicitud
                        FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                        JOIN libro l ON l.isbn=p.isbn
                        WHERE p.estado='solicitado' ORDER BY p.fecha_solicitud""")
        if not sols:
            st.info("No hay solicitudes pendientes.")
        for s in sols:
            with st.container(border=True):
                st.markdown(f"**#{s['id_prestamo']} – {s['titulo']}**  \n"
                            f"Solicita: {s['nombres']} (estado: {s['estado_usuario']}) · {s['fecha_solicitud']}")
                ejs = query("SELECT id_ejemplar, codigo_barras, ubicacion FROM ejemplar "
                            "WHERE isbn=%s AND estado='disponible'", (s["isbn"],))
                c1, c2, c3 = st.columns([3, 2, 2])
                if ejs:
                    opc = {f"{e['codigo_barras']} ({e['ubicacion']})": e["id_ejemplar"] for e in ejs}
                    sel = c1.selectbox("Ejemplar", list(opc), key=f"ej_s{s['id_prestamo']}")
                else:
                    c1.warning("Sin ejemplares disponibles")
                    sel = None
                venc = c2.date_input("Vence", date.today() + timedelta(days=dias), key=f"v_s{s['id_prestamo']}")
                if c3.button("✅ Aprobar", key=f"ap{s['id_prestamo']}", disabled=sel is None):
                    try:
                        run_tx(lambda cur: validar_y_prestar(
                            cur, s["id_usuario"], opc[sel], auth["id"], date.today(), venc,
                            id_prestamo=s["id_prestamo"], isbn=s["isbn"]))
                        st.success("Préstamo aprobado.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        err(e)
                if c3.button("❌ Rechazar", key=f"re{s['id_prestamo']}"):
                    execute("UPDATE prestamo SET estado='rechazado', id_personal=%s WHERE id_prestamo=%s",
                            (auth["id"], s["id_prestamo"]))
                    st.rerun()

    with t2:
        us = query("SELECT id_usuario, codigo, nombres, estado FROM usuario ORDER BY nombres")
        ejs = query("""SELECT e.id_ejemplar, e.codigo_barras, l.titulo FROM ejemplar e
                       JOIN libro l ON l.isbn=e.isbn WHERE e.estado='disponible' ORDER BY l.titulo""")
        if not us or not ejs:
            st.info("Se requieren usuarios y ejemplares disponibles.")
            return
        opc_u = {f"{u['codigo']} – {u['nombres']} ({u['estado']})": u["id_usuario"] for u in us}
        opc_e = {f"{e['codigo_barras']} – {e['titulo']}": e["id_ejemplar"] for e in ejs}
        su = st.selectbox("Usuario", list(opc_u))
        se = st.selectbox("Ejemplar disponible", list(opc_e))
        c1, c2 = st.columns(2)
        fp = c1.date_input("Fecha de préstamo", date.today())
        fv = c2.date_input("Fecha de vencimiento", date.today() + timedelta(days=dias))
        if st.button("Registrar préstamo", type="primary"):
            try:
                run_tx(lambda cur: validar_y_prestar(cur, opc_u[su], opc_e[se], auth["id"], fp, fv))
                st.success("Préstamo registrado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                err(e)


# ======================================================
# Devoluciones
# ======================================================
def pg_devoluciones():
    st.header("↩️ Devoluciones")
    auth = st.session_state["auth"]
    acts = query("""SELECT p.id_prestamo, p.id_ejemplar, u.nombres, l.titulo, ej.codigo_barras,
                           p.fecha_prestamo, p.fecha_vencimiento
                    FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                    JOIN libro l ON l.isbn=p.isbn JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                    WHERE p.estado='activo' ORDER BY p.fecha_vencimiento""")
    if not acts:
        st.info("No hay préstamos activos.")
        return
    opc = {f"#{a['id_prestamo']} – {a['titulo']} ({a['codigo_barras']}) – {a['nombres']}": a for a in acts}
    a = opc[st.selectbox("Préstamo activo", list(opc))]
    f_dev = st.date_input("Fecha de devolución", date.today())
    retraso = max((f_dev - a["fecha_vencimiento"]).days, 0)
    multa = retraso * tarifa_dia()
    if retraso:
        st.warning(f"Retraso: {retraso} día(s) × ${tarifa_dia():,.0f} = **${multa:,.0f}** de multa")
    else:
        st.success("Devolución a tiempo, sin multa.")
    cond = st.selectbox("Estado del ejemplar al devolver", ["bueno", "dañado", "páginas faltantes"])
    obs = st.text_area("Observaciones")
    if st.button("Registrar devolución", type="primary"):
        def tx(cur):
            cur.execute("SELECT estado FROM prestamo WHERE id_prestamo=%s FOR UPDATE", (a["id_prestamo"],))
            if cur.fetchone()["estado"] != "activo":
                raise ValueError("El préstamo ya no está activo.")
            cur.execute("""INSERT INTO devolucion (id_prestamo,id_personal,fecha_devolucion,dias_retraso,
                           multa,condicion,observaciones) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (a["id_prestamo"], auth["id"], f_dev, retraso, multa, cond, obs.strip() or None))
            cur.execute("UPDATE prestamo SET estado='devuelto', fecha_devolucion=%s WHERE id_prestamo=%s",
                        (f_dev, a["id_prestamo"]))
            cur.execute("UPDATE ejemplar SET estado='disponible' WHERE id_ejemplar=%s", (a["id_ejemplar"],))
        try:
            run_tx(tx)
            st.success("Devolución registrada; el ejemplar quedó disponible.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            err(e)

    st.divider()
    st.subheader("Últimas devoluciones")
    show(query("""SELECT d.id_devolucion, l.titulo, u.nombres AS usuario, d.fecha_devolucion,
                         d.dias_retraso, d.multa, d.condicion, d.observaciones
                  FROM devolucion d JOIN prestamo p ON p.id_prestamo=d.id_prestamo
                  JOIN libro l ON l.isbn=p.isbn JOIN usuario u ON u.id_usuario=p.id_usuario
                  ORDER BY d.id_devolucion DESC LIMIT 20"""))


# ======================================================
# Reportes
# ======================================================
def pg_reportes():
    st.header("📊 Reportes")
    t1, t2, t3, t4 = st.tabs(["Activos y vencidos", "Libros más prestados",
                              "Usuarios con más préstamos", "Inventario por estado"])
    with t1:
        rows = query("""SELECT p.id_prestamo, u.nombres AS usuario, l.titulo, ej.codigo_barras,
                               p.fecha_prestamo, p.fecha_vencimiento,
                               IF(p.fecha_vencimiento < CURDATE(),'Vencido','Vigente') AS situacion,
                               GREATEST(DATEDIFF(CURDATE(), p.fecha_vencimiento),0) AS dias_retraso,
                               GREATEST(DATEDIFF(CURDATE(), p.fecha_vencimiento),0) * %s AS multa_estimada
                        FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                        JOIN libro l ON l.isbn=p.isbn JOIN ejemplar ej ON ej.id_ejemplar=p.id_ejemplar
                        WHERE p.estado='activo' ORDER BY p.fecha_vencimiento""", (tarifa_dia(),))
        venc = sum(1 for r in rows if r["situacion"] == "Vencido")
        c1, c2 = st.columns(2)
        c1.metric("Préstamos activos", len(rows))
        c2.metric("Vencidos", venc)
        show(rows, "No hay préstamos activos.")
    with t2:
        c1, c2 = st.columns(2)
        ini = c1.date_input("Desde", date.today() - timedelta(days=90), key="r_ini")
        fin = c2.date_input("Hasta", date.today(), key="r_fin")
        rows = query("""SELECT l.titulo, l.isbn, COUNT(*) AS prestamos
                        FROM prestamo p JOIN libro l ON l.isbn=p.isbn
                        WHERE p.estado IN ('activo','devuelto') AND p.fecha_prestamo BETWEEN %s AND %s
                        GROUP BY l.isbn, l.titulo ORDER BY prestamos DESC LIMIT 10""", (ini, fin))
        show(rows, "Sin préstamos en el periodo.")
        if rows:
            st.bar_chart(to_df(rows).set_index("titulo")["prestamos"])
    with t3:
        rows = query("""SELECT u.codigo, u.nombres, u.rol, COUNT(*) AS prestamos
                        FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
                        WHERE p.estado IN ('activo','devuelto')
                        GROUP BY u.id_usuario, u.codigo, u.nombres, u.rol ORDER BY prestamos DESC LIMIT 10""")
        show(rows, "Sin datos.")
    with t4:
        rows = query("SELECT estado, COUNT(*) AS cantidad FROM ejemplar GROUP BY estado")
        show(rows, "Sin ejemplares.")
        if rows:
            st.bar_chart(to_df(rows).set_index("estado")["cantidad"])


# ======================================================
# Main
# ======================================================
def main():
    st.sidebar.title("📚 Biblioteca")
    if not login_sidebar():
        st.title("Biblioteca Universitaria")
        st.info("Inicia sesión desde el panel lateral.\n\n"
                "• **Personal:** admin / admin123\n\n• **Usuario:** código `U001`, identificación `1001001001`")
        return

    auth = st.session_state["auth"]
    if auth["tipo"] == "personal":
        paginas = {
            "Catálogo": pg_catalogo, "Libros": pg_libros, "Ejemplares": pg_ejemplares,
            "Usuarios": pg_usuarios, "Préstamos": pg_prestamos,
            "Devoluciones": pg_devoluciones, "Reportes": pg_reportes,
        }
    else:
        paginas = {"Catálogo": pg_catalogo, "Mis préstamos": pg_mis_prestamos}
    sel = st.sidebar.radio("Menú", list(paginas))
    try:
        paginas[sel]()
    except pymysql.err.OperationalError as e:
        st.error(f"Error de conexión con MySQL: {e}")


main()
